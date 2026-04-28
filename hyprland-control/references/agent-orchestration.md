# Agent orchestration on Hyprland

This document covers the patterns for using Hyprland as a substrate for multi-agent workflows. The headline scripts (`agent_launch.py`, `agent_cleanup.py`) are documented in SKILL.md; this is the deeper "why" and the long tail.

## Mental model

Treat each subagent as owning a **named slice of desktop state**:

| Resource          | Identifier          | Lifetime                          |
|-------------------|---------------------|-----------------------------------|
| workspace         | `agent-<id>`        | exists while it has a window      |
| windows           | tag `agent-<id>` + workspace `agent-<id>` + pid set | per spawn |
| stdout/stderr     | parent agent's pipe | per process                       |
| disk artefacts    | `/tmp/agent-<id>/…` | parent's responsibility           |

The first three are observable to the user; the last is parent bookkeeping. Hyprland gives you everything you need to enumerate the first three deterministically — there is no need for a parent-side registry beyond "agents I have started."

## Three identifying mechanisms (use all of them)

A single agent's windows can disappear, get reparented, or fail to apply rules. Robust selection uses all three independently and unions the results:

1. **Workspace name** (`agent-<id>`). Set via the `[workspace name:agent-<id> silent]` exec rule. Survives moves *to other workspaces only if* the agent itself moves them — which usually means the agent meant to.
2. **Tag** (`agent-<id>`). Set via `tagwindow +agent-<id>,address:0x…` after the window is observed. Survives workspace moves; a window keeps its tag for life. The most durable identifier.
3. **PID set**. Returned by `agent_launch.py` (and visible on every client object). Survives anything except the process exiting. Useful for `kill -9` on misbehaving windows.

`agent_cleanup.py` matches the union of all three. That's intentional — any one being absent (e.g. a window that never got tagged because the agent crashed mid-launch) is recoverable from the others.

## The race that `agent_launch.py` exists to avoid

The naive sequence —

```bash
hyprctl dispatch exec firefox
sleep 0.3
hyprctl -j clients | jq '.[-1]'
```

— is wrong three ways:

1. **`sleep` is slow** when the window is fast and **wrong** when the window is slow.
2. **`-1` is not "the new window"**; it's the last entry in JSON order, which is layout-dependent.
3. **Multiple agents launching concurrently can't tell their windows apart** because nothing in `clients` says "this is the one I just spawned."

The fix is to subscribe to `.socket2.sock` *before* exec, so the `openwindow` event for your spawn can't be missed, and to filter that event by **workspace name** (which you set via the exec rule and nobody else is using). That's what `agent_launch.py` does.

If the script's matching is too narrow for an exotic case (Electron apps that spawn helper processes, browsers that open a launcher window first, etc.), tighten `--match-class` / `--match-title` rather than reaching for sleep.

## Layouts for a monitoring grid

Hyprland's three layouts and how they fit:

| Layout    | Behavior                                              | Best for                              |
|-----------|-------------------------------------------------------|---------------------------------------|
| `dwindle` | binary-tree split (default)                           | 2–4 agents per monitor                |
| `master`  | one large + N stacked                                 | "main agent + helpers" with one big   |
| floating  | per-window via `togglefloating` or `[float]` rule     | precise grids (deterministic xy)      |

### Pattern A: agent-per-monitor (recommended for 1–4 agents)

```bash
# Pin alice to laptop, bob to external monitor.
hyprctl dispatch moveworkspacetomonitor agent-alice,eDP-2
hyprctl dispatch moveworkspacetomonitor agent-bob,HDMI-A-1
```

Each monitor stays focused on one agent. The user can glance left/right to monitor.

### Pattern B: dwindle grid on one monitor

If you have many agents and one big screen, let dwindle do the work. After spawning N windows on the same workspace they tile automatically. To get a 2x2 from 4 windows you typically want the second to split horizontally and then the third/fourth to split the existing tiles vertically — easiest is to pre-set:

```bash
hyprctl keyword dwindle:force_split 2     # always split right/down predictably
```

Then `agent_launch.py` four times into the same workspace. (This `keyword` setting is session-only.)

### Pattern C: deterministic floating grid

When you want pixel-precise placement (e.g. a 3x3 dashboard), use floating + size + move rules at exec time:

```bash
python scripts/agent_launch.py --agent-id a1 \
  --rule "float" --rule "size 640 360" --rule "move 0 0" \
  --match-class '^firefox$' --tag -- firefox …

python scripts/agent_launch.py --agent-id a2 \
  --rule "float" --rule "size 640 360" --rule "move 640 0" \
  --match-class '^firefox$' --tag -- firefox …
# … and so on
```

The rules apply atomically with the spawn; no post-launch fix-up needed.

### Pattern D: special workspaces as scratchpads

Special workspaces are overlays — toggling shows them on top of whatever's focused, and toggling again hides them without losing the underlying state. Useful for "peek at the agent's progress without leaving my real work":

```bash
# Spawn agent into a special workspace.
python scripts/agent_launch.py --agent-id alice \
  --workspace 'special:alice' --match-class '^firefox$' --tag -- firefox …

# User toggles a peek.
hyprctl dispatch togglespecialworkspace alice
```

A regular workspace can host one agent visibly; a special workspace can host one agent on-demand. Combine for "main agent always visible, side agents available on a hotkey."

## Subscribing to lifecycle events from the parent

If the parent wants to react when a subagent's window opens, closes, or moves, the `.socket2.sock` stream is the right tool. Skeleton (Python, stdlib only):

```python
import os, socket
sig = os.environ["HYPRLAND_INSTANCE_SIGNATURE"]
path = f"{os.environ['XDG_RUNTIME_DIR']}/hypr/{sig}/.socket2.sock"
s = socket.socket(socket.AF_UNIX); s.connect(path)
buf = b""
while True:
    buf += s.recv(4096)
    while b"\n" in buf:
        line, buf = buf.split(b"\n", 1)
        text = line.decode(errors="replace")
        # text is "EVENT>>DATA"
        if text.startswith("closewindow>>"):
            addr = "0x" + text.split(">>", 1)[1]
            handle_close(addr)
```

Events relevant to orchestration: `openwindow`, `closewindow`, `movewindow`, `windowtitle`, `urgent`, `minimize`, `fullscreen`, `screencast`. Full list in `event-ipc.md`.

## Per-agent logging surface

Hyprland doesn't capture spawned-process stdout — the exec dispatcher just `fork()`s. If the parent wants logs, redirect at the command level:

```bash
python scripts/agent_launch.py --agent-id alice ... -- \
  bash -c 'firefox … > /tmp/agent-alice/stdout.log 2> /tmp/agent-alice/stderr.log'
```

For agent processes that read from a pipe, the simplest pattern is to spawn the process directly (not via Hyprland's `exec`), then tell Hyprland post-hoc to move its window once it appears. That's a different tradeoff: you lose the silent-launch race protection but gain stdio. Use the orchestration scripts for the visible "place on screen" part and a normal `subprocess.Popen` for the "drive it" part if you need both.

## Cleanup discipline

Subagents die. Sometimes cleanly, sometimes by panic. Never assume their cleanup ran. The parent should:

1. Always call `agent_cleanup.py --agent-id <id>` in a `finally` block (or its shell `trap` equivalent).
2. On `--kill`, also remove the workspace's leftover state if it had one — empty named workspaces auto-remove when the last window leaves, so usually you don't have to.
3. Verify after: `hyprctl -j clients | jq --arg ag agent-<id> 'any(.[]; (.tags//[]) | index($ag) or .workspace.name == $ag)'` should be `false`.

## Concurrency safety

Multiple parent agents launching multiple subagents at the same time on the same Hyprland session is fine — `hyprctl` serializes through one socket and Hyprland processes dispatch commands atomically. The only contention is the *event stream*: every subscriber sees every event. `agent_launch.py` filters by workspace name, so unless two agents picked the same `agent-id` (a parent bug, not an IPC bug), they will not confuse each other's windows.

If you do need to give every subagent a guaranteed-unique id, use `agent-$$-$(date +%s)` or a UUID. The id is opaque to Hyprland.

## When the agent app doesn't open a window (or opens too many)

- **Headless mode.** Some agent-browsers default to `--headless`. If you wanted a visible monitoring grid, drop the flag — otherwise no window will appear and `agent_launch.py` will time out. The fix is in *your* command, not the skill.
- **Multiple windows.** Browsers often open a launcher window then the real one. Tighten `--match-title` to the URL or app name to land on the right one. Or call `agent_launch.py` once per expected window.
- **WM-ignored windows.** Some apps mark themselves as `override-redirect` or layer-shell surfaces; those don't appear in `clients`. They show up in `hyprctl -j layers` instead. If your agent uses one (e.g. an OSD), this skill can't track it via clients — fall back to pid-based cleanup.

## Anti-patterns

Things that look right but break:

- **Polling `hyprctl clients` for the new window in a loop.** Race-prone, slow, wasteful. Use the event socket.
- **Reusing one workspace across agents.** Defeats the visible-monitoring premise and makes cleanup ambiguous. One workspace per agent id is the contract.
- **Yanking focus on launch.** Forgetting `silent` makes Hyprland focus the new workspace, jerking the user's view. Default to silent; switch focus only when the user asked.
- **Closing by class.** `closewindow class:^firefox$` will close every Firefox window, including the user's. Always close by `address:` or `pid:`.
- **Persisting addresses to disk.** Addresses don't survive the window. Persist `(agent_id, pid, command)` instead and re-resolve via `hyprctl -j clients` when needed.
