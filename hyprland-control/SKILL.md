---
name: hyprland-control
description: |
  Use this skill to drive Hyprland as a programmable desktop — primarily as a substrate for
  multi-agent orchestration where each subagent gets its own workspace and the user's monitors
  become a live agent-monitoring grid. Trigger when the caller wants to: launch a GUI process
  (browser, IDE, terminal, agent-browser, etc.) into a dedicated workspace silently, track that
  window's address/pid for later interaction, tag windows by agent id, list or arrange all
  windows belonging to an agent, or clean up at task end. Also trigger for general Hyprland
  runtime control: inspecting clients/workspaces/monitors as JSON, moving/floating/fullscreening
  windows, batched IPC actions, screenshots (grim+slurp), color picking (hyprpicker), audio
  (wpctl/pamixer), brightness (brightnessctl), media (playerctl), notifications
  (notify-send/makoctl), launcher (walker), lock (hyprlock), and reading current keybindings.
  The skill bundles `scripts/agent_launch.py` (race-free spawn-and-wait) and
  `scripts/agent_cleanup.py` (tag/workspace/pid-scoped teardown) as the headline primitives.
  Do NOT use this skill to edit `~/.config/hypr/*.conf` or other persistent config — runtime
  `hyprctl keyword` changes are session-local; for persistent changes hand off to the `omarchy`
  skill.
---

# Hyprland as a programmable desktop

Hyprland exposes a stable IPC (`hyprctl` + a Unix event socket). Treat it as an SDK, not a UI: every action is scriptable, every piece of state is queryable as JSON, and races are avoidable if you subscribe to events before you act.

This skill's primary use case: **agent orchestration.** A parent agent spawns subagents that each drive a GUI app (an `agent-browser`, a sandboxed IDE, a terminal repro). Each subagent claims a workspace, launches its app there silently, gets back a window address, does its work, and tears down. The user watches everything happen across their monitors.

Secondary use case: general device control (screenshots, audio, brightness, media, notifications, etc).

## Core primitives

```
scripts/agent_launch.py    spawn a process into a per-agent workspace,
                           wait race-free for its window, return JSON.
scripts/agent_cleanup.py   close every window belonging to an agent,
                           by tag / workspace / pid.
scripts/responsive_test.py screenshot a URL at multiple viewport sizes;
                           composes agent_launch + resize + grim.
hyprctl -j <query>         read state as JSON.
hyprctl dispatch <action>  take an action.
hyprctl --batch "...; ..." atomic multi-action.
```

Run scripts with `python scripts/agent_launch.py …` or `./scripts/agent_launch.py …`. They have only stdlib deps.

## Pattern: workspace-per-agent

The convention this skill assumes is **one named workspace per agent, named `agent-<id>`**. Hyprland natively supports named workspaces — there's no allocation table to maintain, the name *is* the namespace. Two agents with the same id share a workspace; two with different ids never collide.

### Spawn an app into an agent's workspace

```bash
python scripts/agent_launch.py \
  --agent-id 42 \
  --match-class '^firefox$' \
  --tag \
  --timeout 15 \
  -- firefox --new-instance https://example.com
```

What happens:
1. Subscribes to the Hyprland event socket *before* dispatching exec (so the `openwindow` event can't be missed).
2. Sends `hyprctl dispatch exec "[workspace name:agent-42 silent] firefox …"`. The `silent` rule keeps the user's focus where it was.
3. Waits up to `--timeout` seconds for an `openwindow` event on `agent-42` whose class matches the regex. Falls back to scanning `hyprctl clients` in case the event was missed (belt + suspenders).
4. With `--tag`, applies tag `agent-42` to the window so it can be found later even if it moves to a different workspace.
5. Prints one JSON line to stdout:

```json
{"address": "0x55ab12cd34ef", "pid": 12345, "class": "firefox",
 "title": "Example Domain - Firefox", "workspace": "agent-42", "tag": "agent-42"}
```

Use that `address` for every subsequent action: `hyprctl dispatch closewindow address:0x55ab…`, etc. Addresses are stable for the window's lifetime.

### Find windows belonging to an agent

A two-line jq is enough:

```bash
hyprctl -j clients | jq --arg ag "agent-42" \
  '.[] | select((.tags // []) | index($ag)) // select(.workspace.name == $ag)'
```

For one-off "give me everything for agent X" calls, this is the right shape — no script needed.

### Tear down

```bash
python scripts/agent_cleanup.py --agent-id 42
# Or, when the app ignores graceful close:
python scripts/agent_cleanup.py --agent-id 42 --kill
# Preview without acting:
python scripts/agent_cleanup.py --agent-id 42 --dry-run
```

Matches by tag *and* workspace *and* explicit pids — whichever applies. Idempotent: matching zero windows is success.

### Pattern: resize a specific window without yanking focus

For driving an existing window's geometry from outside (responsive testing, layout sweeps, deterministic grids), use the `…windowpixel` dispatchers — they take a window selector and don't require focus. The `…active` variants only target the focused window and aren't safe to script in a loop.

```bash
# Float, resize, and place a specific window — atomic, no focus change.
hyprctl --batch "dispatch togglefloating address:0x55ab... ; \
                 dispatch resizewindowpixel exact 375 667,address:0x55ab... ; \
                 dispatch movewindowpixel exact 100 100,address:0x55ab..."
```

Two gotchas:
- `resizewindowpixel` on a *tiled* window adjusts splits, not absolute size. Float the window first (or launch it with `--rule "float"`) if you need an exact pixel size.
- The window dimensions Hyprland reports include any client-side decorations the app draws. The actual content viewport may be a few pixels smaller; use a kiosk/headless flag (`firefox --kiosk`, `chromium --app=URL`, etc.) when you need the window to *be* the viewport.

### Pattern: responsive screenshot sweep

`scripts/responsive_test.py` bundles the launch → resize → grim → cleanup loop into one call. It's the typical use of the resize dispatchers above.

```bash
python scripts/responsive_test.py \
  --url https://example.com \
  --breakpoints mobile=375x667 tablet=768x1024 laptop=1280x800 desktop=1920x1080 \
  --out /tmp/example-shots/ \
  --kiosk
```

Output: one PNG per breakpoint at `/tmp/example-shots/<name>.png`, plus a JSON manifest on stdout listing requested vs actual sizes and per-shot success. Default breakpoints are the four above; pass `WxH` (auto-named) or `NAME=WxH` to override. The script reuses `agent_launch.py` for the race-free spawn and `agent_cleanup.py` for teardown, so it inherits all the orchestration guarantees — runs without disturbing the user's other windows.

Useful flags: `--browser chromium` to swap browsers, `--settle 1.0` to give heavy pages more time to reflow before each capture, `--keep` to leave the browser open for manual inspection, `--browser-arg --headless` if the browser supports it (note: headless windows may not appear on the workspace at all — the script will time out).

### Layout for the monitoring grid

Hyprland's default layout (`dwindle`) tiles windows automatically. To get a deliberate "all agents visible at once" view, the simplest patterns are:

- **One agent per monitor.** `hyprctl dispatch moveworkspacetomonitor agent-42,DP-2`. Pin agent-42 there and the user watches it on the side display.
- **Stacked workspaces, peeked via special.** Use `togglespecialworkspace agent-42` to overlay an agent's workspace temporarily without losing the current focus.
- **Floating tile grid.** Pass `--rule "float"` and `--rule "size 800 600"` and `--rule "move <x> <y>"` to `agent_launch.py`. Hyprland honors these at exec time, so you get deterministic placement.

See `references/agent-orchestration.md` for the full grid + multi-monitor playbook.

## Pattern: read-then-act

Don't act blind. Most failures in IPC orchestration come from assuming a window exists when it doesn't. Cheap checks:

```bash
# Is anything from this agent still around?
hyprctl -j clients | jq --arg ag agent-42 'any(.[]; (.tags // []) | index($ag))'

# What workspace is the user currently looking at? (don't yank focus from them)
hyprctl -j activeworkspace | jq -r .name

# Did my spawn actually land where I said?
hyprctl -j clients | jq --arg a 0x55ab12cd34ef '.[] | select(.address == $a)'
```

When mutating, prefer **address selectors** (`address:0x...`) over class/title regexes — they're unique and don't fire on the wrong window if a name happens to collide.

## hyprctl, in two sentences

`hyprctl -j <noun>` returns JSON state for a noun (clients, workspaces, monitors, devices, layers, binds, …). `hyprctl dispatch <verb> <args>` performs an action; args are comma-separated with **no spaces**, and most verbs accept a window selector (`address:0xHEX`, `pid:N`, `class:^regex$`, `title:regex`, `tag:NAME`, `activewindow`).

Full coverage is in the references — load them when you need depth, not by default:

- `references/agent-orchestration.md` — multi-agent layouts, race-handling, lifecycle, examples
- `references/dispatchers.md` — every `hyprctl dispatch` verb with arg shapes
- `references/queries.md` — every `hyprctl -j` query, JSON shapes, jq recipes
- `references/companion-tools.md` — grim, slurp, wpctl, brightnessctl, playerctl, mako, walker, hyprlock
- `references/event-ipc.md` — the `.socket2.sock` event stream for live reactions

## Other capabilities (one-liners)

These don't fit the orchestration loop but are part of "use the device to its full capacity." Treat them as the standard library — reach for them when the caller asks.

```bash
# Region screenshot to clipboard
grim -g "$(slurp)" - | wl-copy -t image/png

# Active window screenshot to file (geometry from hyprctl)
grim -g "$(hyprctl -j activewindow | jq -r '"\(.at[0]),\(.at[1]) \(.size[0])x\(.size[1])"')" \
  ~/Pictures/win-$(date +%s).png

# Color pick → clipboard as #rrggbb
hyprpicker -a

# Audio
wpctl set-volume @DEFAULT_AUDIO_SINK@ 5%+
wpctl set-mute   @DEFAULT_AUDIO_SOURCE@ toggle      # mic
pamixer --get-volume                                # alt PipeWire client

# Brightness
brightnessctl set 10%+

# Media (MPRIS)
playerctl play-pause
playerctl metadata --format '{{ artist }} - {{ title }}'

# Notifications
notify-send -u normal -t 5000 "Agent 42" "task complete"
makoctl list                                        # JSON of active notifs
makoctl dismiss --all

# Launcher / lock
walker -m drun
hyprlock

# Hyprland's own overlay notification (separate from mako)
hyprctl notify 1 5000 "rgb(00ff00)" "build green"
```

Detail and edge cases for each: `references/companion-tools.md`.

## Runtime config (non-persistent)

`hyprctl keyword <option> <value>` mutates any config option for the current session only. Useful for "try this layout for the agent grid" without touching files:

```bash
hyprctl keyword general:gaps_in 4
hyprctl keyword bind SUPER,F12,exec,python ~/agents/dashboard.py
hyprctl keyword windowrulev2 "tag +agent-42, class:^(firefox)$, title:^(.*Agent 42.*)$"
```

**Always tell the caller these vanish on `hyprctl reload` or session restart.** If they need to persist, hand off to the `omarchy` skill — it owns `~/.config/hypr/*.conf` and the rest of the desktop config.

## Guardrails

- **Confirm before destructive session-wide actions.** `dispatch exit`, `dispatch forcerendererreload`, `closewindow` on windows you didn't spawn, killing the user's focused workspace — all of these can lose work. The agent-orchestration scripts only touch windows matched by agent id, which is the safe default; anything broader needs explicit intent.
- **Don't yank user focus.** Default everything to `silent`. Only switch the user's view (`dispatch workspace …`) when the user asked for it. `agent_launch.py` is silent by default for this reason.
- **Don't poll.** For "wait until X happens", use the event socket (already what `agent_launch.py` does internally). Polling `hyprctl` in a tight loop wastes wakeups and is racier than events.
- **Window addresses are session-local.** Don't persist them across reloads. Tag-based and pid-based lookups survive layout changes; address-based ones only survive while the window exists.
- **Some dispatchers silently no-op.** `focuswindow class:^(does-not-exist)$` returns success and changes nothing. After any consequential dispatch, verify with a query if the next step depends on it.

## End-to-end example: parent agent orchestrating two browser subagents

```bash
# Subagent A starts a browser on its own workspace and gets back a handle.
HANDLE_A=$(python scripts/agent_launch.py \
  --agent-id alice --match-class '^firefox$' --tag --timeout 15 \
  -- firefox --new-instance --kiosk https://news.ycombinator.com)
ADDR_A=$(echo "$HANDLE_A" | jq -r .address)

# Subagent B does the same on a different workspace concurrently.
HANDLE_B=$(python scripts/agent_launch.py \
  --agent-id bob --match-class '^firefox$' --tag --timeout 15 \
  -- firefox --new-instance --kiosk https://en.wikipedia.org)
ADDR_B=$(echo "$HANDLE_B" | jq -r .address)

# Park them side by side: A on the laptop screen, B on the external.
hyprctl dispatch moveworkspacetomonitor agent-alice,eDP-2
hyprctl dispatch moveworkspacetomonitor agent-bob,HDMI-A-1

# Later, screenshot just B's window for the parent's report.
grim -g "$(hyprctl -j clients | jq -r --arg a "$ADDR_B" \
  '.[] | select(.address == $a) | "\(.at[0]),\(.at[1]) \(.size[0])x\(.size[1])"')" \
  /tmp/bob.png

# Clean up everything Alice touched.
python scripts/agent_cleanup.py --agent-id alice
```

Every step is observable from the user's screen, every step is reproducible, every step returns parseable JSON.
