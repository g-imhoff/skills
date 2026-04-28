# Hyprland query reference

All queries below accept `-j` for JSON. Use it. The text output exists for humans skimming a terminal, not for parsing.

## Per-query summary

| Query                  | Returns                                                      |
|------------------------|--------------------------------------------------------------|
| `monitors`             | array of monitors with geometry, scale, focused workspace    |
| `workspaces`           | array of workspaces with id, name, monitor, window count     |
| `activeworkspace`      | the focused workspace object                                 |
| `workspacerules`       | parsed `workspace` config rules                              |
| `clients`              | array of windows                                             |
| `activewindow`         | the focused window                                           |
| `layers`               | layer-shell surfaces (panels, notifications, wallpapers)     |
| `devices`              | mice, keyboards, tablets, touch                              |
| `binds`                | every active keybinding                                      |
| `globalshortcuts`      | desktop-portal global shortcuts                              |
| `animations`           | animation curves and config                                  |
| `cursorpos`            | cursor X,Y                                                   |
| `version`              | hyprland version + commit + flags                            |
| `splash`               | the random splash line                                       |
| `systeminfo`           | OS/GPU/dependency info                                       |
| `getoption <opt>`      | one config option's current value                            |
| `instances`            | running Hyprland instances on this user                      |
| `rollinglog`           | recent Hyprland log lines (handy for debugging)              |
| `decorations <window>` | decoration objects on a window                               |

## Common shapes

### `monitors`
```json
[{
  "id": 0, "name": "HDMI-A-1", "description": "...", "make": "...", "model": "...",
  "width": 2560, "height": 1440, "refreshRate": 165.0,
  "x": 0, "y": 0, "scale": 1.0, "transform": 0,
  "focused": true, "dpmsStatus": true, "vrr": false,
  "activeWorkspace": {"id": 1, "name": "1"},
  "specialWorkspace": {"id": 0, "name": ""}
}]
```

### `clients` (windows)
```json
[{
  "address": "0x55ab12cd34ef",
  "mapped": true, "hidden": false,
  "at": [120, 60], "size": [1280, 720],
  "workspace": {"id": 1, "name": "1"},
  "floating": false, "pseudo": false, "monitor": 0,
  "class": "firefox", "title": "GitHub - …",
  "initialClass": "firefox", "initialTitle": "Firefox",
  "pid": 12345, "xwayland": false,
  "fullscreen": 0, "fullscreenClient": 0,
  "grouped": [], "tags": [], "swallowing": "0x0",
  "focusHistoryID": 0, "inhibitingIdle": false
}]
```

### `binds`
```json
[{
  "locked": false, "mouse": false, "release": false, "repeat": false,
  "longPress": false, "non_consuming": false, "has_description": false,
  "modmask": 64, "submap": "", "key": "Z", "keycode": 0, "catchall": false,
  "description": "", "dispatcher": "killactive", "arg": ""
}]
```

`modmask` decoded: 1=SHIFT, 4=CTRL, 8=ALT, 64=SUPER (logical-or for combos). Easier: just read it as a number and let jq filter on the `key` and `dispatcher`.

## Useful jq recipes

```bash
# Windows on workspace 3, sorted by recency of focus
hyprctl -j clients | jq 'map(select(.workspace.id == 3)) | sort_by(.focusHistoryID)'

# Group window count per workspace
hyprctl -j clients | jq 'group_by(.workspace.id) | map({ws: .[0].workspace.id, n: length})'

# Find a window by partial title
hyprctl -j clients | jq '.[] | select(.title | test("Pull request"; "i"))'

# Active monitor name
hyprctl -j monitors | jq -r '.[] | select(.focused) | .name'

# All keys bound to a workspace dispatcher
hyprctl -j binds | jq '.[] | select(.dispatcher == "workspace") | {key, arg}'

# Geometry string for grim, for the active window
hyprctl -j activewindow | jq -r '"\(.at[0]),\(.at[1]) \(.size[0])x\(.size[1])"'

# All floating windows across all workspaces
hyprctl -j clients | jq '.[] | select(.floating)'

# Is a class currently visible on the focused monitor?
hyprctl -j clients | jq --arg c firefox '
  any(.[]; .class == $c and .mapped and .workspace.id ==
    (input_filename as $_ | (env.WS // 1 | tonumber)))'
```

## getoption

For "what's the current value of X" without parsing the whole config:

```bash
hyprctl -j getoption general:gaps_in        # → {"option": "general:gaps_in", "int": 5, ...}
hyprctl -j getoption decoration:rounding
hyprctl -j getoption animations:enabled
```

The returned object has `int`, `float`, `str`, `data` fields — only the relevant one is populated.

## rollinglog

When something feels off (a binding "doesn't work", a windowrule isn't applying):

```bash
hyprctl rollinglog | tail -50
```

Errors in config parsing show up here even if Hyprland kept running.
