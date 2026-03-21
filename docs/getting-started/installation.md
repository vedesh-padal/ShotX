---
title: Installation Guide — ShotX
description: Learn how to install ShotX on various Linux distributions using source code, PyPI, or community packages.
---

# Installation Guide

## One-liner (Recommended)

```bash
curl -sSL https://raw.githubusercontent.com/vedesh-padal/ShotX/main/install.sh | sh
```

This automatically:

1. Detects your package manager (apt / dnf / pacman / zypper / apk)
2. Installs all system dependencies
3. Installs [uv](https://docs.astral.sh/uv/) if not present
4. Clones ShotX to `~/.local/share/shotx/`
5. Creates a `shotx` launcher at `~/.local/bin/shotx`
6. Adds an XDG autostart entry so ShotX launches on login

!!! note
    `~/.local/bin` must be in your `PATH`. If it isn't, add this to your shell config and restart:

    ```bash
    export PATH="$HOME/.local/bin:$PATH"
    ```

**Env-var overrides for CI / Docker builds:**

```bash
# Skip system dep installation (if you manage deps yourself)
SKIP_SYSTEM_DEPS=1 sh install.sh

# Skip XDG autostart entry creation
SKIP_AUTOSTART=1 sh install.sh
```

---

## From Source (Manual)

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

!!! tip
    You can also use the inclusive `Justfile` or `Makefile` in the root for automated setup and development tasks (e.g., `just setup-deps-debian`, `just sync`).

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

| Package   | Purpose                                  | Install (Ubuntu/Debian)         |
| --------- | ---------------------------------------- | ------------------------------- |
| `xclip`   | Persistent clipboard in X11 CLI mode     | `sudo apt install xclip`        |
| `wl-copy` | Persistent clipboard in Wayland CLI mode | `sudo apt install wl-clipboard` |

### Optional (Feature-Specific)

| Package         | Feature                                | Install (Ubuntu/Debian)          |
| --------------- | -------------------------------------- | -------------------------------- |
| `tesseract-ocr` | OCR text extraction                    | `sudo apt install tesseract-ocr` |
| `libzbar0`      | QR code scanning                       | `sudo apt install libzbar0`      |
| `ffmpeg`        | Screen recording (X11), GIF conversion | `sudo apt install ffmpeg`        |
| `wf-recorder`   | Screen recording (Wayland/wlroots)     | `sudo apt install wf-recorder`   |
| `grim`          | Screenshots on Sway/Hyprland           | `sudo apt install grim`          |
| `slurp`         | Region selection on Sway/Hyprland      | `sudo apt install slurp`         |

<a name="at-spi2-sub-region-auto-detection"></a>

!!! note
    PyGObject is automatically downloaded as a core Python dependency for native DBus notifications. However, if you are building from source, you may need to install the system headers. The exact package name depends on your Ubuntu/Debian version:

    - **Ubuntu 22.04 / Debian 11**: `sudo apt install libcairo2-dev libgirepository1.0-dev pkg-config`
    - **Ubuntu 24.04+ / Debian 12+**: `sudo apt install libcairo2-dev libgirepository-2.0-dev pkg-config`

## PyPI (Coming Soon)

ShotX is not yet published to PyPI. Install from source (above) or watch the [releases page](https://github.com/vedesh-padal/ShotX/releases).
