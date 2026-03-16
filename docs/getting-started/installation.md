# Installation

## From Source (Recommended)

### Prerequisites

- Python 3.10 or later
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- A Linux desktop with Wayland or X11

### Steps

```bash
# Clone the repository
git clone https://github.com/vedesh-padal/ShotX.git
cd ShotX

# Set up with uv
uv venv --python 3.12
uv pip install -e ".[all,dev]"

# Launch
uv run shotx           # System tray mode
uv run shotx --help    # See all CLI options
```

### With pip

```bash
git clone https://github.com/vedesh-padal/ShotX.git
cd ShotX
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[all,dev]"
shotx
```

## System Dependencies

Some features require system packages. ShotX works without them but with reduced functionality.

### Required

| Package      | Purpose | Install                       |
| ------------ | ------- | ----------------------------- |
| Python 3.10+ | Runtime | Pre-installed on most distros |

### Recommended

| Package | Purpose                          | Install (Ubuntu/Debian)  |
| ------- | -------------------------------- | ------------------------ |
| `xclip` | Persistent clipboard in CLI mode | `sudo apt install xclip` |

### Optional (Feature-Specific)

| Package         | Feature                                | Install (Ubuntu/Debian)          |
| --------------- | -------------------------------------- | -------------------------------- |
| `tesseract-ocr` | OCR text extraction                    | `sudo apt install tesseract-ocr` |
| `libzbar0`      | QR code scanning                       | `sudo apt install libzbar0`      |
| `ffmpeg`        | Screen recording (X11), GIF conversion | `sudo apt install ffmpeg`        |
| `wf-recorder`   | Screen recording (Wayland/wlroots)     | `sudo apt install wf-recorder`   |
| `grim`          | Screenshots on Sway/Hyprland           | `sudo apt install grim`          |
| `slurp`         | Region selection on Sway/Hyprland      | `sudo apt install slurp`         |

> **Note:** PyGObject is automatically downloaded as a core Python dependency for native DBus notifications. However, if you are building from source on a distro that does not supply pre-compiled wheels, you may need to install the system headers: `sudo apt install libcairo2-dev libgirepository1.0-dev pkg-config`.

## PyPI (Coming Soon)

```bash
pip install shotx
```
