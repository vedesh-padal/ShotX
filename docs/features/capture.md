# Screen Capture

ShotX supports multiple capture modes, all accessible from the tray menu, Main Window sidebar, hotkeys, or CLI.

## Fullscreen

Captures the entire screen (or a specific monitor in multi-monitor setups).

```bash
shotx --capture-fullscreen
```

**How it works:**

1. Grabs a screenshot via the display server (xdg-desktop-portal on Wayland, XCB on X11)
2. Runs the [after-capture pipeline](#after-capture-pipeline): save → clipboard → upload → notify

## Region

Capture a user-selected rectangular area with an interactive overlay.

```bash
shotx --capture-region
```

**How it works:**

1. Captures a fullscreen backdrop image
2. Detects available regions (windows via compositor API, UI elements via AT-SPI2)
3. Displays a full-screen overlay with:
    - Rubber-band drag selection
    - Hover highlighting on detected regions
    - Dimension labels while dragging
4. On selection: either enters annotation mode or saves directly (configurable)

## Window

Currently uses the same region overlay as region capture — click on a detected window to capture it.

```bash
shotx --capture-window
```

## Capture Options

### Screenshot Delay

Add a configurable delay (in seconds) before capture. Useful for capturing menus, tooltips, or timed states.

Set via Settings → Capture → Screenshot Delay.

### Cursor Visibility

Toggle whether the mouse cursor appears in screenshots.

Set via Settings → Capture → Show Cursor.

### Auto-Detect Regions

Enable/disable automatic detection of windows and UI elements for hover-to-select.

When enabled, ShotX uses:

- **Window enumeration**: compositor-specific APIs (GNOME Introspect, wlroots)
- **AT-SPI2**: Accessibility tree for sub-window UI element detection

!!! note
AT-SPI2 requires PyGObject. See [Installation](../getting-started/installation.md#at-spi2-sub-region-auto-detection) for setup.

## After-Capture Pipeline

The after-capture pipeline is a configurable sequence of actions:

| After-Capture Task | What it does | Default |
| :--- | :--- | :--- |
| Save to File      | Save screenshot to output directory | ✅ On   |
| Copy to Clipboard | Send image bytes to system clipboard | ✅ On   |
| Upload Image      | Trigger the background upload engine | ❌ Off  |
| Open in Editor    | Launch internal drawing tool        | ❌ Off  |

> [!NOTE] Disk Spooling Fallback
> The **Upload** and **Editor** tools fundamentally require a physical file path to read or transmit image bytes. If you have "Save to file" **unchecked** but still request an Upload or Edit action, ShotX will automatically save a silent, high-quality temporary file to `/tmp/shotx/` so the background workers don't crash. Since Linux automatically clears the `/tmp` RAM-disk upon reboot or memory pressure, no manual cleanup is required!

Configure via Main Window sidebar → After Capture Tasks, or Settings → Workflow.
