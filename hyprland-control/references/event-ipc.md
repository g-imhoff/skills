# Hyprland event IPC

Hyprland exposes two Unix sockets per running instance, under
`$XDG_RUNTIME_DIR/hypr/$HYPRLAND_INSTANCE_SIGNATURE/`:

- `.socket.sock` — what `hyprctl` writes to (request/response). Don't bother using this directly; `hyprctl` is the right interface.
- `.socket2.sock` — read-only event stream. One event per line: `EVENT>>DATA`.

Use the event socket only when you genuinely need to *react* to changes — e.g. a long-running watcher. For one-shot questions, just `hyprctl -j` query and be done.

## Reading events

```bash
SOCK="$XDG_RUNTIME_DIR/hypr/$HYPRLAND_INSTANCE_SIGNATURE/.socket2.sock"
socat -u "UNIX-CONNECT:$SOCK" -
```

If `socat` isn't installed, `nc -U "$SOCK"` works too (depending on the netcat flavor).

## Common events

| Event             | Data                                    |
|-------------------|-----------------------------------------|
| `workspace`       | `<workspace name>`                      |
| `focusedmon`      | `<monitor>,<workspace>`                 |
| `activewindow`    | `<class>,<title>`                       |
| `activewindowv2`  | `<address>`                             |
| `openwindow`      | `<address>,<workspace>,<class>,<title>` |
| `closewindow`     | `<address>`                             |
| `movewindow`      | `<address>,<workspace>`                 |
| `fullscreen`      | `0` / `1`                               |
| `monitoradded`    | `<name>`                                |
| `monitorremoved`  | `<name>`                                |
| `submap`          | `<name>` (empty when leaving)           |
| `urgent`          | `<address>`                             |
| `minimize`        | `<address>,<state>`                     |
| `screencast`      | `<state>,<owner>` (1=start, 0=end)      |

(Full list: <https://wiki.hyprland.org/IPC/>. Don't fetch the wiki unless something's missing here.)

## Patterns

**React to workspace switch** — e.g. for a custom waybar module:

```bash
SOCK="$XDG_RUNTIME_DIR/hypr/$HYPRLAND_INSTANCE_SIGNATURE/.socket2.sock"
socat -u "UNIX-CONNECT:$SOCK" - | while IFS= read -r line; do
  case "$line" in
    workspace\>\>*) echo "switched to ${line#workspace>>}" ;;
  esac
done
```

**Notify when a specific app opens**:

```bash
socat -u "UNIX-CONNECT:$SOCK" - | awk -F'>>' '
  $1 == "openwindow" {
    split($2, a, ",")
    if (a[3] == "firefox") system("notify-send Firefox opened")
  }'
```

**Watch active window changes** (cheap; one event per focus change):

```bash
socat -u "UNIX-CONNECT:$SOCK" - | grep --line-buffered '^activewindow>>'
```

## When to prefer this over polling

Polling `hyprctl -j activewindow` in a loop is wasteful and slow to react. The event socket is the right answer when:

- You want to update a status bar / overlay on focus/workspace change.
- You want to apply per-window logic at open time (a poor man's `windowrulev2 = onworkspace…`).
- You need to log session activity.

For one-off "what's focused right now", a single `hyprctl -j activewindow` is correct.
