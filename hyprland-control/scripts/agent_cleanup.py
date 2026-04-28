#!/usr/bin/env python3
"""
agent_cleanup — close every window associated with an agent.

Selection rules (any can match):
  * windows tagged 'agent-<id>'                 (preferred — set by --tag in agent_launch)
  * windows on workspace 'agent-<id>' (or --workspace)
  * windows whose pid is in --pid (repeatable)

By default uses Hyprland's `closewindow` (graceful). Use --kill to send
SIGKILL by pid instead (useful for agents whose UI ignores close requests).

Output: JSON list of the windows acted on, with what method was used.

Exit codes:
  0   matched and acted (or matched zero — also OK; idempotent by design)
  3   hyprctl/IPC error
  64  bad invocation
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys


def hyprctl(*args: str, json_out: bool = False) -> str:
    cmd = ["hyprctl"]
    if json_out:
        cmd.append("-j")
    cmd.extend(args)
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"agent_cleanup: hyprctl {' '.join(args)} failed: {r.stderr.strip()}",
              file=sys.stderr)
        sys.exit(3)
    return r.stdout


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Close all windows belonging to an agent (by tag, "
                    "workspace, or pid).",
    )
    p.add_argument("--agent-id", required=True,
                   help="Agent identifier. Matches tag 'agent-<id>' and "
                        "workspace 'agent-<id>' by default.")
    p.add_argument("--workspace",
                   help="Override the workspace name to match. Defaults to "
                        "agent-<id>. Pass empty string to skip workspace match.")
    p.add_argument("--pid", action="append", type=int, default=[],
                   help="Additional pid to match. Repeatable.")
    p.add_argument("--kill", action="store_true",
                   help="SIGKILL pids instead of asking the WM to close.")
    p.add_argument("--dry-run", action="store_true",
                   help="Print the would-be actions but do nothing.")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    tag = f"agent-{args.agent_id}"
    workspace = args.workspace if args.workspace is not None else f"agent-{args.agent_id}"

    clients = json.loads(hyprctl("clients", json_out=True))

    matched = []
    for c in clients:
        why = []
        if tag in (c.get("tags") or []):
            why.append("tag")
        if workspace and c.get("workspace", {}).get("name") == workspace:
            why.append("workspace")
        if c.get("pid") in args.pid:
            why.append("pid")
        if why:
            matched.append({"client": c, "matched_on": why})

    actions = []
    for m in matched:
        c = m["client"]
        action = {
            "address": c["address"],
            "pid": c.get("pid"),
            "class": c.get("class"),
            "title": c.get("title"),
            "matched_on": m["matched_on"],
        }
        if args.dry_run:
            action["method"] = "dry-run"
        elif args.kill and c.get("pid"):
            try:
                os.kill(c["pid"], signal.SIGKILL)
                action["method"] = "sigkill"
            except ProcessLookupError:
                action["method"] = "sigkill-already-gone"
            except PermissionError as e:
                action["method"] = f"sigkill-error:{e}"
        else:
            hyprctl("dispatch", "closewindow", f"address:{c['address']}")
            action["method"] = "closewindow"
        actions.append(action)

    print(json.dumps({"agent_id": args.agent_id, "actions": actions,
                      "count": len(actions)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
