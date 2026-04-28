# Hyprland dispatchers reference

Dispatchers run via `hyprctl dispatch <name> <args>`. Args are comma-separated, **no spaces** around commas. Many accept a window selector as the trailing arg.

## Window selectors

Use these wherever a dispatcher takes a "window" argument. The leading `,` is part of the syntax — the dispatcher's own positional args come first, then `,selector`.

| Selector            | Meaning                                              |
|---------------------|------------------------------------------------------|
| `address:0xHEX`     | window's IPC address (from `hyprctl -j clients`)     |
| `pid:N`             | match by process pid                                 |
| `class:REGEX`       | regex on app class — anchor with `^(...)$`           |
| `initialClass:REGEX`| class at window creation time                        |
| `title:REGEX`       | regex on title                                       |
| `initialTitle:REGEX`| title at window creation                             |
| `tag:NAME`          | user-applied tag                                     |
| `floating`          | only floating windows                                |
| `tiled`             | only tiled windows                                   |
| `activewindow`      | the focused window                                   |

## Workspaces

| Dispatcher                       | Args                                                | Notes |
|----------------------------------|-----------------------------------------------------|-------|
| `workspace`                      | `N` / `+1` / `-1` / `e+1` (existing only) / `name:foo` / `previous` | switch focus |
| `movetoworkspace`                | `N,window` — also follows focus to that workspace   |       |
| `movetoworkspacesilent`          | `N,window` — keep focus where it is                 |       |
| `renameworkspace`                | `N,newName`                                         |       |
| `togglespecialworkspace`         | `[name]` — show/hide a "scratchpad" workspace       |       |
| `focusworkspaceoncurrentmonitor` | `N` — pick a workspace on the focused monitor only  |       |
| `movecurrentworkspacetomonitor`  | `monitor` — name (e.g. `HDMI-A-1`) or `+1`/`-1`     |       |
| `moveworkspacetomonitor`         | `workspace,monitor`                                 |       |

## Window state

| Dispatcher          | Args                                          | Notes |
|---------------------|-----------------------------------------------|-------|
| `killactive`        | —                                             | close focused window |
| `closewindow`       | `window`                                      | close any window |
| `togglefloating`    | `[window]`                                    | active if omitted |
| `fullscreen`        | `0` real / `1` maximize / `2` toggle off      | acts on active |
| `fullscreenstate`   | `internal,client` — values: -1 keep, 0 none, 1 max, 2 fs, 3 fs+max | finer control |
| `pin`               | `[window]`                                    | float window pinned across workspaces |
| `pseudo`            | `[window]`                                    | toggle "pseudotiled" |
| `centerwindow`      | `[1]`                                         | center floating window; `1` respects monitor reserved area |
| `tagwindow`         | `tag,[window]`                                | set/unset tags; prefix with `+`/`-` |

## Movement and focus

| Dispatcher          | Args                                          | Notes |
|---------------------|-----------------------------------------------|-------|
| `movefocus`         | `l` / `r` / `u` / `d`                         | directional focus |
| `movewindow`        | `direction` or `mon:NAME`                     | move within layout / to monitor |
| `swapwindow`        | `l` / `r` / `u` / `d`                         | swap with neighbor |
| `focuswindow`       | `window`                                      | jump focus |
| `focusmonitor`      | `mon` — name or `+1`/`-1`                     |       |
| `focuscurrentorlast`| —                                             | toggle last focused |
| `swapnext`          | `prev` / `next`                               | swap with master/next |
| `cyclenext`         | `prev` / `next` / `tiled` / `floating`        | cycle focus |
| `moveactive`        | `dx dy` (px) or `exact X Y`                   | move floating window (focused only) |
| `resizeactive`      | `dw dh` or `exact W H`                        | resize active (focused only) |
| `movewindowpixel`   | `dx dy,window` or `exact X Y,window`          | move any window — no focus required |
| `resizewindowpixel` | `dw dh,window` or `exact W H,window`          | resize any window — no focus required (use this in scripts) |
| `splitratio`        | `+0.1` / `-0.1` / `exact 0.6`                 | adjust dwindle/master split |

## Groups (tabbed windows)

| Dispatcher              | Args                                       | Notes |
|-------------------------|--------------------------------------------|-------|
| `togglegroup`           | —                                          | group/ungroup the active window |
| `changegroupactive`     | `b` / `f`                                  | cycle within group |
| `lockactivegroup`       | `lock` / `unlock` / `toggle`               |       |
| `moveintogroup`         | `direction`                                |       |
| `moveoutofgroup`        | —                                          |       |

## Cursor

| Dispatcher              | Args                                       |
|-------------------------|--------------------------------------------|
| `movecursortocorner`    | `0` BL, `1` BR, `2` TR, `3` TL             |
| `movecursor`            | `X Y` absolute                             |

## Misc

| Dispatcher              | Args                                          | Notes |
|-------------------------|-----------------------------------------------|-------|
| `exec`                  | `[[rules]] command...`                        | spawn anything; rules in `[[ ]]` like `[[workspace 3]] kitty` |
| `execr`                 | command                                       | exec without rules |
| `exit`                  | —                                             | **ends session** — confirm first |
| `forcerendererreload`   | —                                             | last-resort GPU refresh |
| `bringactivetotop`      | —                                             |       |
| `alterzorder`           | `top` / `bottom`                              |       |
| `sendshortcut`          | `MODS,key,window`                             | inject key into target window |
| `pass`                  | `window`                                      | pass the next key to a window |
| `global`                | `name:keyword`                                | trigger app-defined global shortcut |
| `setprop`               | `window prop value [lock]`                    | per-window override (e.g. `rounding`, `bordersize`) |

## Examples

```bash
# Float pavucontrol whenever it appears, this session only
hyprctl keyword windowrule "float, ^(pavucontrol)$"

# Move the active firefox window to special:web and toggle the special workspace
hyprctl --batch "dispatch movetoworkspacesilent special:web,class:^(firefox)$ ; dispatch togglespecialworkspace web"

# Resize active window to a fixed size and re-center it
hyprctl --batch "dispatch resizeactive exact 1200 800 ; dispatch centerwindow 1"

# Send Ctrl+Shift+T into Firefox (reopen closed tab)
hyprctl dispatch sendshortcut CTRL_SHIFT,t,class:^(firefox)$

# Spawn kitty on workspace 3 already maximized
hyprctl dispatch exec "[[workspace 3 ; fullscreen 1]] kitty"
```
