# Makefile for ShotX Developer Operations
# Standard compatibility layer for those without 'just' installed.

.PHONY: setup-deps-debian sync lint typecheck test run help

# Default target: show help
help:
	@echo "Available targets:"
	@echo "  setup-deps-debian : Install system dependencies (Ubuntu/Debian)"
	@echo "  sync              : Synchronize python environment with uv"
	@echo "  lint              : Run ruff check"
	@echo "  typecheck         : Run mypy"
	@echo "  test              : Run pytest headlessly"
	@echo "  run               : Run ShotX locally"

setup-deps-debian:
	sudo apt-get update
	sudo apt-get install -y \
		libcairo2-dev pkg-config gobject-introspection \
		libglib2.0-dev libgirepository-2.0-dev \
		xvfb libegl1 libgl1 libopengl0 \
		libxcb-cursor0 libxcb-icccm4 libxcb-image0 \
		libxcb-keysyms1 libxcb-randr0 libxcb-render-util0 \
		libxcb-shape0 libxcb-xfixes0 libxcb-xinerama0 \
		libxcb-xkb1 libxkbcommon-x11-0 libdbus-1-3

sync:
	uv sync --all-groups

lint:
	uv run ruff check src/ tests/

typecheck:
	uv run mypy src/

test:
	xvfb-run -a uv run pytest tests/

run:
	uv run -m shotx.main
