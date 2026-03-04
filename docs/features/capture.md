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

| Action            | Description                         | Default |
| ----------------- | ----------------------------------- | ------- |
| Save to File      | Save screenshot to output directory | ✅ On   |
| Copy to Clipboard | Copy image to system clipboard      | ✅ On   |
| Upload Image      | Upload to configured destination    | ❌ Off  |
| Open in Editor    | Open in the image editor            | ❌ Off  |

Configure via Main Window sidebar → After Capture Tasks, or Settings → Workflow.
