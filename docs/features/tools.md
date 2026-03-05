# Productivity Tools

ShotX includes several standalone tools accessible from the tray menu, Main Window, or CLI.

## OCR (Text Extraction)

Select a screen region and extract text using Tesseract OCR.

```bash
shotx --ocr
```

**Flow:** Select region → Tesseract processes → extracted text copied to clipboard → notification shown.

!!! note "Requires `tesseract-ocr`"
Install: `sudo apt install tesseract-ocr`

## Color Picker

A magnifier overlay that lets you pick the exact hex color of any pixel on screen.

```bash
shotx --color-picker
```

**Flow:** Magnifier follows cursor → click to pick → hex color (e.g. `#FF5733`) copied to clipboard.

## Screen Ruler

Measure pixel distances and boundaries on screen.

```bash
shotx --ruler
```

**Flow:** Full-screen overlay → drag to measure → displays distance in pixels.

## QR Code

### Scan from Screen

Select a screen region containing a QR code to decode it.

```bash
shotx --qr-scan
```

### Scan from Clipboard

Decode a QR code from the current clipboard image.

```bash
shotx --qr-scan-clipboard
```

### Generate from Clipboard

Generate a QR code image from clipboard text.

```bash
shotx --qr-generate
```

!!! note "Requires `libzbar0`"
QR scanning requires zbar. Install: `sudo apt install libzbar0`

## Pin to Screen

Capture a region and pin it as a floating always-on-top window.

```bash
shotx --pin-region
```

**Controls:**

- Drag to move
- Resize from bottom-right corner handle
- Double-click to close
- Right-click for context menu (Copy, Save, Close)

## Hash Checker

File integrity verification tool supporting MD5, SHA-1, SHA-256, and SHA-512.

```bash
shotx --hash
```

**Features:**

- Drag-and-drop file support
- Compare two hashes for equality
- Copy hash values to clipboard

## Directory Indexer

Generate a styled HTML index of a directory tree.

```bash
shotx --index-dir                # Open dialog
shotx --index-dir ~/projects     # Start at specific path
```

**Features:**

- Interactive directory tree
- File size and type information
- Styled HTML output
- Copy or save the generated index

## Capture History

Browse all past captures with thumbnails, metadata, and actions.

```bash
shotx --history
```

**Features:**

- Async thumbnail loading
- Infinite scroll
- Context menu: open, upload, edit, delete
- Search and filter (coming soon)
