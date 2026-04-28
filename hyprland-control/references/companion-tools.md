# Companion CLI reference

The tools that fill in the gaps Hyprland's IPC doesn't cover. All of these are confirmed installed on this user's setup.

## grim — screenshot capture

`grim` writes a PNG of all or part of the Wayland output. It does not pick the region itself — it pairs with `slurp` (which lets the user drag a selection) or with explicit geometry.

```bash
grim out.png                           # all outputs (rare; usually you want one monitor)
grim -o HDMI-A-1 out.png               # one monitor by name
grim -g "X,Y WxH" out.png              # explicit region
grim -g "$(slurp)" out.png             # interactive region selection
grim -                                  # write to stdout (pipe to wl-copy)
```

Typical recipes (also in SKILL.md):

```bash
# Region → clipboard
grim -g "$(slurp)" - | wl-copy -t image/png

# Active window → file (geometry from hyprctl)
grim -g "$(hyprctl -j activewindow | jq -r '"\(.at[0]),\(.at[1]) \(.size[0])x\(.size[1])"')" \
  ~/Pictures/win-$(date +%s).png

# Focused monitor → clipboard
grim -o "$(hyprctl -j monitors | jq -r '.[] | select(.focused).name')" - | wl-copy -t image/png
```

`slurp` flags worth knowing:
- `slurp -d` — display dimensions while dragging
- `slurp -p` — single-point picker (one pixel coord), use `slurp -p` then read `X,Y 1x1` for grim
- `slurp -o` — pick a whole output by clicking it

## wl-copy / wl-paste — Wayland clipboard

```bash
echo hi | wl-copy                  # set
wl-copy -p                          # primary selection (middle-click)
wl-copy -t image/png < shot.png     # set with a MIME type
wl-paste                            # read text
wl-paste -t image/png > out.png     # read with MIME
wl-paste --list-types               # see what's available
wl-copy --clear                     # clear
```

There's no clipboard *history* tool installed (no cliphist/clipman). If the user wants history, suggest installing `cliphist` and adding the wiring — but that's a config change, hand off to omarchy.

## hyprpicker — eyedropper

```bash
hyprpicker                          # print to stdout (#aabbcc)
hyprpicker -a                       # auto-copy to clipboard
hyprpicker -f hex                   # hex (default)
hyprpicker -f rgb                   # rgb(r,g,b)
hyprpicker -f cmyk                  # cmyk
hyprpicker -n                       # no zoom indicator (less intrusive)
hyprpicker -r                       # render surface (for screenshare apps that miss it)
```

## wpctl (PipeWire) — audio

`wpctl` is the canonical audio control on PipeWire systems. Targets are device IDs, or the special `@DEFAULT_AUDIO_SINK@` / `@DEFAULT_AUDIO_SOURCE@`.

```bash
wpctl status                                          # full graph
wpctl get-volume @DEFAULT_AUDIO_SINK@                # → "Volume: 0.45"
wpctl set-volume @DEFAULT_AUDIO_SINK@ 5%+
wpctl set-volume @DEFAULT_AUDIO_SINK@ 5%-
wpctl set-volume @DEFAULT_AUDIO_SINK@ 0.5            # absolute (0.0–1.0)
wpctl set-volume -l 1.5 @DEFAULT_AUDIO_SINK@ 1.4     # allow >100% (max 1.5)
wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle
wpctl set-mute @DEFAULT_AUDIO_SOURCE@ toggle         # mic mute
wpctl set-default <id>                                # switch default sink/source
```

`pamixer` is also installed if you prefer a more direct API for absolute percentages:

```bash
pamixer --get-volume
pamixer -i 5     # +5%
pamixer -d 5     # -5%
pamixer -t       # toggle mute
pamixer --get-mute
```

## brightnessctl — backlight

```bash
brightnessctl                        # show all devices + current
brightnessctl get
brightnessctl set 50%
brightnessctl set 10%+
brightnessctl set 10%-
brightnessctl --device=intel_backlight set 80%
brightnessctl --device=smc::kbd_backlight set 30%   # keyboard backlight if present
brightnessctl -m                     # machine-readable: device,class,value,max,percent
brightnessctl -s                     # save current; -r restore
```

## playerctl — MPRIS media

Targets MPRIS-compliant players (Spotify, Firefox, mpv, VLC, etc).

```bash
playerctl status                             # Playing / Paused / Stopped
playerctl play / pause / play-pause / next / previous / stop
playerctl position                           # current position in seconds
playerctl position 30+                       # seek +30s
playerctl volume                             # 0.0-1.0
playerctl volume 0.1+
playerctl metadata                           # all metadata
playerctl metadata --format '{{ artist }} - {{ title }}'
playerctl --player=spotify play              # one player
playerctl -a status                          # all players
playerctl -l                                 # list players
playerctl -F status                          # follow status changes (long-running)
```

## notify-send / makoctl — notifications

`notify-send` fires a notification through whatever daemon is listening (mako here):

```bash
notify-send "Title" "Body text"
notify-send -u low|normal|critical "Title" "Body"
notify-send -t 5000 "Auto-dismiss" "in 5s"
notify-send -i dialog-information "Title" "with icon"
notify-send -A "yes=Yes" -A "no=No" "Continue?" "..."   # actions; reads chosen id on stdout
notify-send -h string:x-canonical-private-synchronous:foo "..."  # replaces previous "foo"
```

`makoctl` controls mako (the notification daemon) directly — read state, dismiss, trigger actions:

```bash
makoctl list                       # JSON of current notifications
makoctl dismiss                    # dismiss the topmost
makoctl dismiss --all
makoctl dismiss -n <id>
makoctl invoke <id> [action]       # default action if action omitted
makoctl restore                    # restore one from history
makoctl menu                       # action-menu picker (needs a dmenu-like)
makoctl mode                       # show current mode
makoctl mode -a do-not-disturb     # add a mode (config decides what it does)
makoctl mode -r do-not-disturb
makoctl reload                     # re-read mako config
```

## walker — launcher

Walker is the launcher on this setup (omarchy default). Runs in different modes:

```bash
walker                  # default (drun)
walker -m drun          # desktop apps
walker -m run           # any binary on PATH
walker -m websearch     # web search engines
walker -m calc          # quick calculator
walker -m emojis        # emoji picker → clipboard
walker -m ssh           # ssh hosts
walker -m clipboard     # clipboard history (only if wired up)
walker -m windows       # window switcher (uses hyprctl)
```

`-q "query"` pre-fills the query. `-d` runs in daemon mode (already set up by omarchy autostart).

## hyprlock — screen lock

```bash
hyprlock                  # lock immediately, blocking until unlocked
hyprlock --immediate      # skip the fade-in
hyprlock --no-fade-in
```

For "lock then suspend" you'd usually do `hyprlock & sleep 0.3 && systemctl suspend` — but that's a system action, confirm first.

## What's NOT installed (but commonly expected)

If a recipe online assumes one of these, swap to the installed equivalent:

| Tool the user *doesn't* have | Use this instead              |
|------------------------------|-------------------------------|
| `wlr-randr`                  | `hyprctl monitors` + `hyprctl keyword monitor=...` |
| `hyprshot`                   | `grim` + `slurp` (see recipes) |
| `rofi`                       | `walker`                       |
| `swaync`                     | `mako` (already used)          |
| `swaylock`                   | `hyprlock`                     |
| `cliphist`                   | not installed; suggest install if user wants clipboard history |
