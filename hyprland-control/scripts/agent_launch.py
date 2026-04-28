#!/usr/bin/env python3
"""
agent_launch — race-free GUI launch for a single agent.

Reserves an agent's workspace, spawns a process via Hyprland's `exec` dispatcher
with an inline `[workspace name:... silent]` rule (so the user's focus is not
yanked), then waits on the Hyprland event socket for the corresponding
`openwindow` event and returns its address. Optionally tags the window with the
agent id so siblings can find it later.

Output: a single JSON object on stdout, e.g.
  {"address": "0x55...", "pid": 12345, "class": "firefox", "title": "...",
   "workspace": "agent-42", "tag": "agent-42"}

Exit codes:
  0   window appeared and is reported on stdout
  2   timeout — no matching window appeared in --timeout seconds
  3   hyprctl/IPC error
  64  bad invocation
"""

from __future__ import annotations

import argparse
import json
import os
import re
import socket
import subprocess
import sys
import time
from pathlib import Path


def hypr_socket_dir() -> Path:
    runtime = os.environ.get("XDG_RUNTIME_DIR")
    sig = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")
    if not runtime or not sig:
        die(3, "XDG_RUNTIME_DIR and HYPRLAND_INSTANCE_SIGNATURE must be set "
               "(are you running inside a Hyprland session?)")
    p = Path(runtime) / "hypr" / sig
    if not p.is_dir():
        die(3, f"hyprland socket dir does not exist: {p}")
    return p


def die(code: int, msg: str) -> "None":
    print(f"agent_launch: {msg}", file=sys.stderr)
    sys.exit(code)


def hyprctl(*args: str, json_out: bool = False) -> str:
    cmd = ["hyprctl"]
    if json_out:
        cmd.append("-j")
    cmd.extend(args)
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        die(3, f"hyprctl {' '.join(args)} failed: {r.stderr.strip()}")
    return r.stdout


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Launch a GUI command into a per-agent workspace and "
                    "return its window address once it appears.",
    )
    p.add_argument("--agent-id", required=True,
                   help="Stable identifier for the agent. Used as the default "
                        "workspace name and (with --tag) as the window tag.")
    p.add_argument("--workspace",
                   help="Override the workspace name (default: agent-<id>).")
    p.add_argument("--match-class",
                   help="Regex matched against the new window's class. "
                        "Defaults to '.*' (first window to appear wins).")
    p.add_argument("--match-title",
                   help="Optional regex on title. Combined with --match-class.")
    p.add_argument("--timeout", type=float, default=10.0,
                   help="Seconds to wait for the window to appear (default 10).")
    p.add_argument("--tag", action="store_true",
                   help="Apply tag 'agent-<id>' to the window once seen.")
    p.add_argument("--no-silent", action="store_true",
                   help="Drop the 'silent' rule so launching also focuses the "
                        "agent's workspace. Default is silent.")
    p.add_argument("--rule", action="append", default=[],
                   help="Extra Hyprland exec rules, e.g. --rule 'float' "
                        "--rule 'size 1200 800'. Repeatable.")
    p.add_argument("command", nargs=argparse.REMAINDER,
                   help="Command to spawn (after `--`).")
    args = p.parse_args()
    if args.command and args.command[0] == "--":
        args.command = args.command[1:]
    if not args.command:
        die(64, "missing command (put it after `--`).")
    return args


def build_exec_arg(workspace: str, silent: bool, extra_rules: list[str],
                   command: list[str]) -> str:
    rules = [f"workspace name:{workspace}"]
    if silent:
        rules[-1] += " silent"
    rules.extend(extra_rules)
    rule_block = " ; ".join(rules)
    # `hyprctl dispatch exec` takes a single string. We pass through
    # subprocess as a list, so quoting is on us only for the inner command.
    quoted = " ".join(_shell_quote(c) for c in command)
    return f"[{rule_block}] {quoted}"


def _shell_quote(s: str) -> str:
    if not s or any(ch in s for ch in " \t\n\"'\\$`!*?[]{}()<>|&;#"):
        return "'" + s.replace("'", "'\\''") + "'"
    return s


def watch_openwindow(timeout: float):
    """Yield (address, workspace, klass, title) for each openwindow event."""
    sock_path = hypr_socket_dir() / ".socket2.sock"
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(timeout)
    s.connect(str(sock_path))
    buf = b""
    deadline = time.monotonic() + timeout
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return
        s.settimeout(remaining)
        try:
            chunk = s.recv(4096)
        except socket.timeout:
            return
        if not chunk:
            return
        buf += chunk
        while b"\n" in buf:
            line, buf = buf.split(b"\n", 1)
            text = line.decode(errors="replace")
            if not text.startswith("openwindow>>"):
                continue
            data = text[len("openwindow>>"):]
            parts = data.split(",", 3)
            if len(parts) < 4:
                continue
            addr, ws, klass, title = parts
            yield f"0x{addr}" if not addr.startswith("0x") else addr, ws, klass, title


def find_existing(match_class: re.Pattern, match_title: re.Pattern | None,
                  workspace: str) -> dict | None:
    """Race fallback: scan current clients in case the window appeared
    between launch and us subscribing."""
    try:
        clients = json.loads(hyprctl("clients", json_out=True))
    except json.JSONDecodeError:
        return None
    for c in clients:
        if c.get("workspace", {}).get("name") != workspace:
            continue
        if not match_class.search(c.get("class", "")):
            continue
        if match_title and not match_title.search(c.get("title", "")):
            continue
        return c
    return None


def main() -> int:
    args = parse_args()
    workspace = args.workspace or f"agent-{args.agent_id}"
    match_class = re.compile(args.match_class or ".*")
    match_title = re.compile(args.match_title) if args.match_title else None

    # Subscribe BEFORE exec to avoid the race where the window opens and
    # disappears from the event stream before we connect.
    sock_path = hypr_socket_dir() / ".socket2.sock"
    sub = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sub.connect(str(sock_path))
    sub.setblocking(False)

    exec_arg = build_exec_arg(
        workspace=workspace,
        silent=not args.no_silent,
        extra_rules=args.rule,
        command=args.command,
    )
    hyprctl("dispatch", "exec", exec_arg)

    deadline = time.monotonic() + args.timeout
    buf = b""
    found: dict | None = None
    poll_interval = 0.05

    while time.monotonic() < deadline and not found:
        try:
            chunk = sub.recv(4096)
            if chunk:
                buf += chunk
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    text = line.decode(errors="replace")
                    if not text.startswith("openwindow>>"):
                        continue
                    parts = text[len("openwindow>>"):].split(",", 3)
                    if len(parts) < 4:
                        continue
                    addr, ws, klass, title = parts
                    if ws != workspace:
                        continue
                    if not match_class.search(klass):
                        continue
                    if match_title and not match_title.search(title):
                        continue
                    found = {"address": addr if addr.startswith("0x") else f"0x{addr}",
                             "workspace": ws, "class": klass, "title": title}
                    break
        except BlockingIOError:
            pass
        if found:
            break
        # Belt-and-suspenders: also scan clients in case we missed the event.
        existing = find_existing(match_class, match_title, workspace)
        if existing:
            found = {"address": existing["address"], "workspace": workspace,
                     "class": existing["class"], "title": existing["title"]}
            break
        time.sleep(poll_interval)

    sub.close()

    if not found:
        die(2, f"timed out after {args.timeout:.1f}s waiting for a window on "
               f"workspace '{workspace}' matching class={match_class.pattern!r}"
               + (f" title={match_title.pattern!r}" if match_title else ""))

    # Pull the full client object so we can include pid and confirm state.
    clients = json.loads(hyprctl("clients", json_out=True))
    client = next((c for c in clients if c["address"] == found["address"]), None)
    if client is None:
        # Window vanished between event and query. Still return what we have.
        result = found | {"pid": None}
    else:
        result = {
            "address": client["address"],
            "pid": client.get("pid"),
            "class": client.get("class"),
            "title": client.get("title"),
            "workspace": client.get("workspace", {}).get("name"),
        }

    if args.tag:
        tag = f"agent-{args.agent_id}"
        hyprctl("dispatch", "tagwindow", f"+{tag},address:{result['address']}")
        result["tag"] = tag

    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
