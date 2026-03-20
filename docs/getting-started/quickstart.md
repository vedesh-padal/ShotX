# Quick Start

## Tray Mode (Primary)

Launch ShotX as a system tray application:

```bash
shotx
# or
shotx --tray
```

Right-click the tray icon to access all features: capture, tools, recording, upload, and settings.

## CLI One-Shot Mode

Run a single command and exit:

=== "Capture"

    ```bash
    shotx --capture-fullscreen    # Full screen
    shotx --capture-region        # Select a region
    shotx --capture-window        # Select a window
    ```

=== "Tools"

    ```bash
    shotx --ocr                   # OCR: region → text to clipboard
    shotx --color-picker          # Pick a color → hex to clipboard
    shotx --ruler                 # Measure pixel distances
    shotx --qr-scan               # Scan QR from screen
    shotx --pin-region            # Pin region as floating window
    ```

=== "Editors"

    ```bash
    shotx --edit                  # Open image editor
    shotx --edit photo.png        # Edit a specific image
    shotx --hash                  # Open hash checker
    shotx --index-dir ~/projects  # Index a directory
    shotx --history               # Browse capture history
    ```

## Main Window

Click the tray icon or select **Open Main Window** from the tray menu to access the unified ShotX hub with:

- **Sidebar navigation** for all capture types, tools, and upload options
- **Capture history** with thumbnails and infinite scroll
- **After-capture pipeline** toggles (save, clipboard, upload, open editor)
- **Settings** for capture, upload, hotkeys, and more

## Configuration

Settings are stored in `~/.config/shotx/settings.yaml` and can be edited via the Settings dialog or directly.

See [Settings Reference](../configuration/settings.md) for all options.
