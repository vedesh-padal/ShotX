# ShotX

**A free, open-source screenshot and screen capture tool for Linux — inspired by [ShareX](https://getsharex.com).**

ShotX brings the power of ShareX to the Linux desktop: instant screen capture, region selection with auto-detect, annotation tools, screen recording, image editing, OCR, and upload to multiple destinations — all from a single hotkey press or system tray.

## What Can ShotX Do?

| Category     | Features                                                                          |
| ------------ | --------------------------------------------------------------------------------- |
| **Capture**  | Fullscreen, region (with auto-detect), configurable delay, cursor toggle          |
| **Annotate** | Arrows, shapes, text, blur, highlight, step numbers — during capture or in editor |
| **Record**   | Screen recording to MP4 or GIF with audio capture                                 |
| **Upload**   | Imgur, ImgBB, tmpfiles.org, S3, FTP/SFTP, custom `.sxcu` uploaders                |
| **Edit**     | Crop, resize, effects, beautifier, combiner                                       |
| **Tools**    | OCR, color picker, ruler, QR code, hash checker, pin-to-screen, directory indexer |

## Quick Example

```bash
# Launch the system tray app
shotx

# One-shot capture from CLI
shotx --capture-fullscreen
shotx --capture-region
shotx --ocr
```

## Get Started

- [Installation Guide](getting-started/installation.md): Set up ShotX from source or PyPI
- [Quick Start](getting-started/quickstart.md): Start capturing in under a minute

## Platform Support

ShotX is **Wayland-first** with full X11 fallback:

- **Wayland**: xdg-desktop-portal D-Bus API (GNOME, KDE, Sway, Hyprland)
- **X11**: XCB/Xlib capture backend

!!! note "Alpha Status"
ShotX is under active development. Core features are complete and stable, with documentation and packaging improvements ongoing.
