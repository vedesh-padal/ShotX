# Justfile for ShotX Developer Operations

# Lists all available recipes
default:
    @just --list

# Install system dependencies for Debian/Ubuntu (Development & CI)
setup-deps-debian:
    sudo apt-get update
    sudo apt-get install -y \
        libcairo2-dev \
        pkg-config \
        gobject-introspection \
        libglib2.0-dev \
        libgirepository-2.0-dev \
        xvfb \
        libegl1 \
        libgl1 \
        libopengl0 \
        libxcb-cursor0 \
        libxcb-icccm4 \
        libxcb-image0 \
        libxcb-keysyms1 \
        libxcb-randr0 \
        libxcb-render-util0 \
        libxcb-shape0 \
        libxcb-xfixes0 \
        libxcb-xinerama0 \
        libxcb-xkb1 \
        libxkbcommon-x11-0 \
        libdbus-1-3

# Synchronize the Python environment using uv
sync:
    uv sync --all-groups

# Run all linting checks (ruff)
lint:
    uv run ruff check src/ tests/

# Run type checks (mypy)
typecheck:
    uv run mypy src/

# Run the test suite headlessly using xvfb
test:
    xvfb-run -a uv run pytest tests/

test-dev:
    uv run pytest tests/

# Run the application locally
run:
    uv run -m shotx.main
