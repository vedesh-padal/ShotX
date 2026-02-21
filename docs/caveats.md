# ShotX — Caveats & Platform Notes

Collected during development. Use for README, GitHub Wiki, and troubleshooting docs.

---

## Wayland Capture

### GNOME Screenshot Portal (`interactive=true`)

- **Why:** GNOME denies `interactive=false` for non-privileged apps (response code 2: "Permission denied"). Must use `interactive=true`, which shows GNOME's native screenshot picker.
- **UX impact:** User sees GNOME's picker before our overlay. Two-step flow.
- **Portal temp file:** GNOME saves the screenshot to `~/Pictures/Screenshots/`. Our code deletes this temp file after loading into memory (wayland.py, `_capture_via_portal`).
- **Clipboard side-effect:** GNOME also copies the fullscreen screenshot to clipboard. We can't prevent this (no portal option exists). Our cropped region overwrites it as the most recent entry, but clipboard managers (CopyQ, GPaste) will show both in history.

### GNOME Shell Introspect (`GetWindows`)

- **Blocked on GNOME 49:** `org.gnome.Shell.Introspect.GetWindows` returns "GetWindows is not allowed" for non-privileged apps. This was our intended source for window positions on Wayland.
- **Workaround:** AT-SPI2 provides window positions via the accessibility tree as an alternative.

### ScreenCast Portal (evaluated, not used)

- **Recording indicator:** GNOME shows a persistent red recording indicator in the top bar when using ScreenCast, even for a single-frame capture. Bad UX for a screenshot tool.
- **Requires `python3-gi` + GStreamer:** Frame extraction from PipeWire streams needs GStreamer bindings.
- **`persist_mode=2`:** Allows reusing a `restore_token` to skip the permission dialog on subsequent captures. But the recording indicator still shows.

### `org.gnome.Shell.Screenshot` D-Bus API

- **Blocked on GNOME 49:** Returns "Screenshot is not allowed" for non-privileged apps.

### `grim` (wlroots fallback)

- Works on Sway, Hyprland, and other wlroots-based compositors.
- **Not available on GNOME** (GNOME uses its own compositor, not wlroots).

---

## Clipboard

### Wayland Clipboard Ownership Model

- **Problem:** On Wayland, the app that sets clipboard content must stay alive to serve paste requests. In one-shot CLI mode (`shotx --capture-region`), the process exits immediately and clipboard data is lost.
- **Solution:** Use subprocess clipboard tools (`wl-copy`, `xclip`, `xsel`) via `Popen`. These fork background processes that persist clipboard data. Falls back to Qt clipboard (works in tray mode where app stays alive).
- **`xclip` behavior:** `xclip` blocks waiting for paste requests — must use `Popen` (not `subprocess.run`) and let it run in background.
- **Runtime dependency:** `xclip` (or `wl-copy`/`xsel`) recommended for one-shot mode. Not required — graceful fallback to Qt clipboard.

---

## AT-SPI2 (Accessibility-based Region Detection)

### PyGObject Dependency

- `python3-gi` (PyGObject) is a C extension that requires system headers to compile.
- **System build deps:** `libgirepository1.0-dev`, `libcairo2-dev`, `pkg-config`
- **pip install:** `pip install PyGObject` compiles from source against system headers. Works with any Python version.
- **System package:** `sudo apt install python3-gi gir1.2-atspi-2.0` — pre-compiled but locked to system Python version. Requires `--system-site-packages` venv flag.
- **Fully optional:** Code gracefully degrades — region capture works with manual drag selection if AT-SPI2 is not available.

### Coverage

- **Good:** GTK apps, Qt apps, Electron apps (partial)
- **Partial:** Browser content (web pages have limited accessibility exposure)
- **None:** Games, custom rendering engines

### `uv` and System Packages

- `uv` uses its own managed Python (e.g., cpython-3.12.12), separate from system Python.
- `--system-site-packages` in a uv-managed venv sees uv's Python site-packages, NOT `/usr/lib/python3/dist-packages/`.
- To use system `python3-gi` directly: `uv venv --python /usr/bin/python3 --system-site-packages`
- Preferred path: install system headers + `pip install PyGObject` (works with any Python).
- `system-site-packages` is NOT a valid `[tool.uv]` key in `pyproject.toml`.

---

## D-Bus

### `dbus-next` Introspection Bug

- `dbus_next`'s high-level proxy API fails to introspect interfaces with hyphenated property names (e.g., `xdg-desktop-portal` properties).
- **Workaround:** Use low-level `Message` API to construct D-Bus calls manually, bypassing introspection.

---

## Qt / PySide6

### `QShortcut` Import Location

- In PySide6 6.10, `QShortcut` moved from `PySide6.QtWidgets` to `PySide6.QtGui`.

### QPainter Lifecycle

- Don't call `painter.end()` explicitly in `paintEvent()` — Qt manages it via RAII when the painter goes out of scope.
- Don't call `self.update()` immediately before `self.close()` — causes overlapping paint events and `QBackingStore::endPaint()` errors, potentially SIGSEGV.

---

## Packaging (Future)

### Distribution Formats

- **`.deb`:** Declare `python3-gi`, `gir1.2-atspi-2.0`, `xclip` as `Recommends`
- **Flatpak:** GNOME Runtime includes PyGObject and AT-SPI2 automatically
- **AppImage:** Bundle `.so` files inside the image
- **Snap:** Declare stage-packages

### Runtime Dependencies (for end users)

| Dependency                    | Purpose                           | Required?                |
| ----------------------------- | --------------------------------- | ------------------------ |
| PySide6                       | UI framework                      | Yes                      |
| dbus-next                     | Portal D-Bus communication        | Yes (Wayland)            |
| xclip / wl-copy               | Persistent clipboard in CLI mode  | Recommended              |
| python3-gi + gir1.2-atspi-2.0 | Sub-region auto-detection         | Optional                 |
| grim                          | Screenshot on wlroots compositors | Optional (Sway/Hyprland) |
