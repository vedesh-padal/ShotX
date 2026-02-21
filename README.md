# ShotX

**A free, open-source screenshot and screen capture tool for Linux — inspired by [ShareX](https://getsharex.com).**

ShotX aims to bring the power of ShareX to the Linux desktop: instant screen capture, region selection with auto-detect, annotation tools, screen recording, and upload to 80+ destinations — all from a single hotkey press.

> 🚧 **Status: Pre-Alpha** — Under active development. See the [Roadmap](#roadmap) below.

## Features (Planned)

- 📷 **Screen Capture** — Fullscreen, region, window, auto-detect on hover
- ✏️ **Annotation** — Arrows, text, blur, highlight, shapes — right in the capture overlay
- 🎥 **Screen Recording** — Record video or GIF of any region
- ☁️ **Upload** — Imgur, S3, Google Drive, FTP, custom uploaders (.sxcu compatible)
- 🔤 **OCR** — Extract text from any screen region
- 🎨 **Image Editor** — Crop, effects, beautify, combine, split
- 🛠️ **Tools** — Color picker, ruler, QR code, hash checker, pin-to-screen
- ⌨️ **Hotkeys** — Configurable global shortcuts
- 🖥️ **Wayland + X11** — First-class support for both display servers

## Requirements

- Linux (Ubuntu 22.04+, Fedora 38+, Arch, Debian 12+, or similar)
- Wayland or X11 session

## Installation

### From Source (Development)

```bash
# Clone the repository
git clone https://github.com/vedesh-padal/ShotX.git
cd shotx

# Set up with uv (recommended)
uv venv --python 3.12
uv pip install -e ".[dev]"

# Run
uv run shotx
```

### AppImage (Coming Soon)

Download the latest `.AppImage` from [Releases](https://github.com/vedesh-padal/ShotX/releases), make it executable, and run. No dependencies required.

## Usage

```bash
# Launch as system tray app (primary mode)
shotx

# Quick capture via CLI
shotx --capture-fullscreen
shotx --capture-region          # Coming in Phase 2
shotx --capture-window          # Coming in Phase 2

# Other options
shotx --version
shotx --help
```

## Roadmap

- [x] **Phase 0** — Project foundation
- [ ] **Phase 1** — Core capture (fullscreen, save, clipboard, tray, hotkeys)
- [ ] **Phase 2** — Region capture with auto-detect overlay
- [ ] **Phase 3** — Annotation tools
- [ ] **Phase 4** — Screen recording (video + GIF)
- [ ] **Phase 5** — Upload engine (Imgur, S3, FTP, custom)
- [ ] **Phase 6** — Workflow & productivity tools
- [ ] **Phase 7** — Image editor
- [ ] **Phase 8** — Polish & distribution (AppImage, Flatpak, DEB)

## Tech Stack

| Component        | Technology                                   |
| ---------------- | -------------------------------------------- |
| Language         | Python 3.10+                                 |
| GUI Framework    | Qt6 / PySide6                                |
| Config           | YAML                                         |
| Screen Capture   | xdg-desktop-portal (Wayland), XCB/Xlib (X11) |
| Recording        | FFmpeg                                       |
| OCR              | Tesseract / PaddleOCR                        |
| Image Processing | Pillow + QPainter                            |

## Contributing

Contributions are welcome! This project follows clean engineering practices:

- Each commit does one thing
- Clear commit messages following conventional commits
- Code is linted with `ruff` and type-checked with `mypy`
- All new features include tests

```bash
# Run tests
uv run pytest

# Lint
uv run ruff check src/

# Type check
uv run mypy src/
```

## License

GPL-3.0 — see [LICENSE](LICENSE) for details. Same license as ShareX.

## Acknowledgments

- [ShareX](https://getsharex.com) — the original inspiration
- [SnapX](https://github.com/SnapXL/SnapX) — the cross-platform hard fork
- [Flameshot](https://flameshot.org) — a great Linux screenshot tool that paved the way
