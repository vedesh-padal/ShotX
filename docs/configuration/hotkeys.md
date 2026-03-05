# Hotkeys

ShotX supports configurable global keyboard shortcuts for common actions.

## Configuring Hotkeys

### Via Settings Dialog

1. Open Main Window → Settings → Hotkey Settings
2. Click the key field next to the action
3. Press the desired key combination
4. Click Save

### Via settings.yaml

Edit `~/.config/shotx/settings.yaml`:

```yaml
hotkeys:
    capture_fullscreen: "Print"
    capture_region: "Alt+Shift+X"
    capture_window: ""
    capture_ocr: "Alt+Shift+O"
    capture_color_picker: "Alt+Shift+Q"
    capture_ruler: ""
    capture_qr_scan: ""
    pin_region: ""
```

## Available Hotkeys

| Action             | Default         | Description                     |
| ------------------ | --------------- | ------------------------------- |
| Fullscreen Capture | (none)          | Capture entire screen           |
| Region Capture     | ++alt+shift+x++ | Select and capture a region     |
| Window Capture     | (none)          | Capture a window                |
| OCR                | (none)          | Extract text from screen region |
| Color Picker       | ++alt+shift+q++ | Pick a color from screen        |
| Ruler              | (none)          | Measure pixel distances         |
| QR Scan            | (none)          | Scan QR code from screen        |
| Pin Region         | (none)          | Pin a region as floating window |

## Key Format

Use Qt-style key names separated by `+`:

- Modifiers: `Ctrl`, `Alt`, `Shift`, `Meta` (Super/Win key)
- Keys: `A`-`Z`, `F1`-`F12`, `Print`, `Home`, `End`, etc.

Examples: `Alt+Shift+X`, `Ctrl+Print`, `F5`

!!! warning "Wayland Limitation"
On Wayland, applications cannot globally intercept keyboard shortcuts due to security isolation. Hotkeys only work when the ShotX window/tray is focused.

**Workaround:** Configure your desktop environment to run ShotX CLI commands as custom keyboard shortcuts:

| Desktop    | Where to configure                                                             |
| ---------- | ------------------------------------------------------------------------------ |
| GNOME      | Settings → Keyboard → Custom Shortcuts                                         |
| KDE Plasma | System Settings → Shortcuts → Custom Shortcuts                                 |
| Sway       | `~/.config/sway/config`: `bindsym Print exec shotx --capture-fullscreen`       |
| Hyprland   | `~/.config/hypr/hyprland.conf`: `bind = , Print, exec, shotx --capture-region` |
