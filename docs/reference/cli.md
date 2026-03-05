# CLI Reference

Complete reference for all ShotX command-line options.

## Synopsis

```
shotx [OPTIONS]
```

If no options are given, ShotX launches in system tray mode.

## Options

### General

| Flag                | Description                                                |
| ------------------- | ---------------------------------------------------------- |
| `--help`            | Show help message and exit                                 |
| `--version`         | Show version number and exit                               |
| `--tray`            | Launch the system tray app (default)                       |
| `--config-dir PATH` | Override the config directory (default: `~/.config/shotx`) |
| `--verbose`         | Enable debug logging                                       |

### Capture

| Flag                   | Description                         |
| ---------------------- | ----------------------------------- |
| `--capture-fullscreen` | Capture entire screen and exit      |
| `--capture-region`     | Select a region to capture and exit |
| `--capture-window`     | Select a window to capture and exit |

### Productivity Tools

| Flag                  | Description                                         |
| --------------------- | --------------------------------------------------- |
| `--ocr`               | Select a region and extract text (OCR) to clipboard |
| `--color-picker`      | Open magnifier to pick a pixel color to clipboard   |
| `--ruler`             | Open screen ruler to measure pixel distances        |
| `--qr-scan`           | Select a region and scan for QR code                |
| `--qr-generate`       | Generate QR code from clipboard text                |
| `--qr-scan-clipboard` | Scan clipboard image for QR code                    |
| `--pin-region`        | Capture region and pin as floating window           |

### Standalone Tools

| Flag                 | Description                                 |
| -------------------- | ------------------------------------------- |
| `--hash`             | Open the hash checker dialog                |
| `--index-dir [PATH]` | Open directory indexer (optionally at PATH) |
| `--edit [IMAGE]`     | Open image editor (optionally with IMAGE)   |
| `--history`          | Open capture history viewer                 |

### Upload

| Flag                  | Description                                                              |
| --------------------- | ------------------------------------------------------------------------ |
| `--shorten-url [URL]` | Shorten a URL. Reads clipboard if no URL given. Prints result to stdout. |

## Exit Codes

| Code | Meaning                    |
| ---- | -------------------------- |
| `0`  | Success                    |
| `1`  | Failure or unknown command |

## Examples

```bash
# Capture fullscreen with debug output
shotx --capture-fullscreen --verbose

# Shorten a URL from CLI (headless, prints to stdout)
shotx --shorten-url "https://example.com/long/path"

# Open editor with an existing image
shotx --edit ~/Pictures/screenshot.png

# Index a project directory
shotx --index-dir ~/projects/myapp

# Use a custom config directory
shotx --tray --config-dir ~/.config/shotx-dev
```
