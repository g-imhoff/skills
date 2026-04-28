#!/usr/bin/env python3
"""
responsive_test — sweep a URL through viewport breakpoints, one screenshot each.

Composes `agent_launch.py` (race-free spawn into a dedicated workspace) with
Hyprland's no-focus-jerk resize dispatchers (`resizewindowpixel`,
`movewindowpixel`) and `grim` for capture.

Output: one PNG per breakpoint at <out>/<name>.png plus a JSON manifest on
stdout summarizing the run.

Exit codes:
  0   all breakpoints captured
  2   spawn timed out (browser window never appeared)
  3   hyprctl/IPC error
  4   one or more grim captures failed
  64  bad invocation
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
AGENT_LAUNCH = SCRIPT_DIR / "agent_launch.py"
AGENT_CLEANUP = SCRIPT_DIR / "agent_cleanup.py"


def die(code: int, msg: str) -> "None":
    print(f"responsive_test: {msg}", file=sys.stderr)
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


def parse_breakpoint(s: str) -> tuple[str, int, int]:
    """Accept '375x667' (auto-named) or 'mobile=375x667'."""
    name, sep, dims = s.partition("=")
    if not sep:
        dims = name
        name = dims  # auto-named like '375x667'
    m = re.fullmatch(r"\s*(\d+)\s*x\s*(\d+)\s*", dims)
    if not m:
        raise argparse.ArgumentTypeError(
            f"breakpoint must be WxH or NAME=WxH, got {s!r}")
    return name.strip(), int(m.group(1)), int(m.group(2))


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Screenshot a URL at multiple viewport sizes via Hyprland.",
    )
    p.add_argument("--url", required=True, help="URL to load.")
    p.add_argument(
        "--breakpoints", nargs="+", type=parse_breakpoint,
        default=[parse_breakpoint(s) for s in
                 ("mobile=375x667", "tablet=768x1024",
                  "laptop=1280x800", "desktop=1920x1080")],
        help="Breakpoints as WxH or NAME=WxH. "
             "Default: mobile, tablet, laptop, desktop.")
    p.add_argument("--out", default=None,
                   help="Output directory. Default: /tmp/responsive-<ts>/.")
    p.add_argument("--browser", default="firefox",
                   help="Browser binary (default: firefox). Must support "
                        "--new-instance / --kiosk semantics if you pass --kiosk.")
    p.add_argument("--agent-id", default=None,
                   help="Agent id (default: responsive-<ts>). Sets workspace "
                        "name and tag.")
    p.add_argument("--match-class", default=None,
                   help="Regex on the new window's class. Default: ^<browser>$.")
    p.add_argument("--launch-timeout", type=float, default=20.0,
                   help="Seconds to wait for the browser window to appear.")
    p.add_argument("--settle", type=float, default=0.5,
                   help="Seconds to wait after each resize before grim, so "
                        "CSS reflow and lazy-loaded assets settle (default 0.5).")
    p.add_argument("--kiosk", action="store_true",
                   help="Pass --kiosk to the browser so chrome (toolbars, "
                        "scrollbars) doesn't eat into the viewport. Browser-"
                        "specific behavior; check your browser supports it.")
    p.add_argument("--position", default="100,100",
                   help="X,Y position of the floating window (default 100,100).")
    p.add_argument("--keep", action="store_true",
                   help="Don't tear down the browser at the end. Useful for "
                        "manual inspection. Otherwise cleanup runs always.")
    p.add_argument("--browser-arg", action="append", default=[],
                   help="Extra arg to pass to the browser. Repeatable.")
    return p.parse_args()


def launch_browser(agent_id: str, url: str, browser: str,
                   match_class: str, timeout: float, kiosk: bool,
                   extra_args: list[str]) -> dict:
    cmd = [sys.executable, str(AGENT_LAUNCH),
           "--agent-id", agent_id,
           "--match-class", match_class,
           "--tag",
           "--timeout", str(timeout),
           "--rule", "float",
           "--", browser, "--new-instance"]
    if kiosk:
        cmd.append("--kiosk")
    cmd.extend(extra_args)
    cmd.append(url)
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode == 2:
        die(2, f"agent_launch timed out: {r.stderr.strip()}")
    if r.returncode != 0:
        die(3, f"agent_launch failed (exit {r.returncode}): {r.stderr.strip()}")
    try:
        return json.loads(r.stdout.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError):
        die(3, f"agent_launch produced no JSON handle. stdout={r.stdout!r}")


def cleanup(agent_id: str) -> None:
    subprocess.run(
        [sys.executable, str(AGENT_CLEANUP), "--agent-id", agent_id],
        capture_output=True, text=True,
    )


def resize_and_move(address: str, w: int, h: int, x: int, y: int) -> None:
    # Batched so the resize+move land in one layout pass — and keeps focus
    # untouched (no resizeactive/moveactive). Both dispatchers exist in
    # Hyprland 0.40+; 0.54 is fine.
    hyprctl(
        "--batch",
        f"dispatch resizewindowpixel exact {w} {h},address:{address} ; "
        f"dispatch movewindowpixel exact {x} {y},address:{address}",
    )


def get_geometry(address: str) -> tuple[int, int, int, int]:
    clients = json.loads(hyprctl("clients", json_out=True))
    for c in clients:
        if c["address"] == address:
            x, y = c["at"]
            w, h = c["size"]
            return x, y, w, h
    die(3, f"window {address} no longer present (closed mid-run?)")
    return 0, 0, 0, 0  # unreachable, satisfies type checker


def shoot(geom: tuple[int, int, int, int], out_path: Path) -> bool:
    x, y, w, h = geom
    geom_str = f"{x},{y} {w}x{h}"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(["grim", "-g", geom_str, str(out_path)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(f"responsive_test: grim failed for {out_path.name}: "
              f"{r.stderr.strip()}", file=sys.stderr)
        return False
    if out_path.stat().st_size == 0:
        print(f"responsive_test: grim produced empty file at {out_path}",
              file=sys.stderr)
        return False
    return True


def main() -> int:
    args = parse_args()
    if not shutil.which("grim"):
        die(3, "grim not found on PATH")
    if not shutil.which(args.browser):
        die(64, f"browser binary {args.browser!r} not found on PATH")

    ts = time.strftime("%Y%m%d-%H%M%S")
    agent_id = args.agent_id or f"responsive-{ts}"
    match_class = args.match_class or f"^{re.escape(args.browser)}$"
    out_dir = Path(args.out) if args.out else Path(f"/tmp/responsive-{ts}")

    try:
        x_str, _, y_str = args.position.partition(",")
        x_pos, y_pos = int(x_str), int(y_str)
    except ValueError:
        die(64, f"--position must be 'X,Y', got {args.position!r}")

    handle = launch_browser(
        agent_id=agent_id, url=args.url, browser=args.browser,
        match_class=match_class, timeout=args.launch_timeout,
        kiosk=args.kiosk, extra_args=args.browser_arg,
    )
    address = handle["address"]

    shots: list[dict] = []
    failures = 0
    try:
        for name, w, h in args.breakpoints:
            resize_and_move(address, w, h, x_pos, y_pos)
            time.sleep(args.settle)
            x, y, gw, gh = get_geometry(address)
            out_path = out_dir / f"{name}.png"
            ok = shoot((x, y, gw, gh), out_path)
            shot = {
                "name": name,
                "requested": [w, h],
                "actual": [gw, gh],
                "path": str(out_path),
                "ok": ok,
            }
            shots.append(shot)
            if not ok:
                failures += 1
    finally:
        if not args.keep:
            cleanup(agent_id)

    manifest = {
        "url": args.url,
        "agent_id": agent_id,
        "browser": args.browser,
        "kiosk": args.kiosk,
        "out_dir": str(out_dir),
        "kept_alive": args.keep,
        "shots": shots,
    }
    print(json.dumps(manifest, indent=2))
    return 0 if failures == 0 else 4


if __name__ == "__main__":
    sys.exit(main())
