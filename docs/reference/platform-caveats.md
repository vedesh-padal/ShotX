---
title: Platform Caveats — Wayland & Desktop Environments
description: Known platform-specific issues and configuration tips for different display servers and desktop portals.
---

# Platform Caveats & Known Limitations

Known platform-specific behaviors, workarounds, and limitations discovered during development.

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

## Screen Recording

### Subprocess Wrapper Strategy

- Since continuously pulling frames from Wayland requires complex PipeWire negotiation (which GNOME usually restricts behind a user-prompting portal anyway), ShotX delegates screen recording to proven CLI tools via `subprocess.Popen`.

### Record Backends

- **X11:** Uses `ffmpeg -f x11grab`. Works flawlessly for both region and fullscreen recording.
- **Wayland (wlroots):** Uses `wf-recorder` (which uses the `wlr-screencopy` protocol). Works flawlessly on Sway, Hyprland, etc.
- **Wayland (GNOME):** GNOME heavily restricts programmatic region recording (`wf-recorder` relies on `wlr-screencopy` which GNOME Mutter refuses to implement). The only way to record on GNOME is via the XDG Desktop Portal and PipeWire. However, GNOME's portal forces a disruptive security popup ("Share this screen with ShotX?") on _every single recording_, breaking the "instant capture" UX goal.
    - **Decision:** Because of the massive architectural complexity (GStreamer/PipeWire in Python) and the poor resultant UX, this feature is pushed to **Phase 9**. For now, GNOME Wayland users receive a helpful warning advising them to use GNOME's built-in recorder (`Ctrl+Shift+Alt+R`) or switch to an X11 session.

### GIF Recording

- ShotX records an MP4 stream first to a temporary file, then runs an `ffmpeg` post-processing pass using `palettegen` and `paletteuse` to generate highly optimized, high-quality GIFs.

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

| Dependency                    | Purpose                           | Required?                          |
| ----------------------------- | --------------------------------- | ---------------------------------- |
| PySide6                       | UI framework                      | Yes                                |
| dbus-next                     | Portal D-Bus communication        | Yes (Wayland)                      |
| xclip / wl-copy               | Persistent clipboard in CLI mode  | Recommended                        |
| python3-gi + gir1.2-atspi-2.0 | Sub-region auto-detection         | Optional                           |
| grim                          | Screenshot on wlroots compositors | Optional (Sway/Hyprland)           |
| wf-recorder                   | Screen Recording on Wayland       | Optional (Wayland wlroots)         |
| ffmpeg                        | Screen Recording / GIF Generation | Optional (X11 recording & all GIF) |

---

## GNOME Wayland & Qt System Tray Notifications

### Qt `messageClicked` Signal Dropped

- **Issue:** On GNOME Wayland, Qt `QSystemTrayIcon.showMessage()` properly displays notifications via the FreeDesktop standard, but GNOME intentionally swallows the `messageClicked` callback. It never returns the DBus click signal back to the Qt application event loop. Thus, notifications become completely dead logic black holes—you can click them, but Qt never, ever knows.

### Focus-Stealing Prevention (Silent Notifications)

- **Secondary Issue:** Background applications lacking active window focus will have their notifications silently dumped into the GNOME tray by default, bypassing the visual pop-down banner entirely.

### PyGObject Native DBus Workaround

- **Solution:** We completely uncoupled notifications from `QSystemTrayIcon` in `notification.py`.
- **Implementation:**
    1. We import `gi.repository.Gio` (PyGObject) to pipe raw zero-overhead DBus calls directly to `org.freedesktop.Notifications.Notify` using `Gio.DBusConnection.call_sync()`.
    2. We physically subscribe a global Python handler to `ActionInvoked` DBus signals and dynamically match the returned DBus `notification_id` to our saved screenshot file paths.
    3. To defeat the GNOME focus limitation, we explicitly inject `{"urgency": 2}` (Critical) hints into all of our DBus payloads so that ShotX notifications are strictly displayed as pop-down banners immediately upon capture.

## "Always on Top" (Pinned Snippets)

- **The Issue:** On GNOME Wayland, applications are strictly forbidden from programmatically forcing themselves above other windows. This is a security measure to prevent "UI hijacking."
- **Behavior in ShotX:** The **Pin to Screen** feature uses the `Qt.WindowStaysOnTopHint`. On most compositors (KDE Plasma, Sway), this works as expected. On GNOME, it is "best effort"—the compositor may push the snippet to the background if you focus a full-screen window.
- **Future Fix:** We are exploring a dedicated GNOME Shell Extension (Phase 10+) to handle pinning at the compositor level.

## Global Hotkeys

- **The Issue:** Wayland does not allow apps to "spy" on global keystrokes.
- **Solution:** ShotX uses the `XDG Global Shortcuts` portal where available, or relies on system-level keybindings (e.g., mapping `Print` to `shotx --capture-region`).

## Window Repositioning

- **The Issue:** Wayland prevents apps from knowing their absolute global coordinates or moving themselves to specific pixel locations (e.g., `window.move(x, y)`).
- **Solution:** ShotX uses `windowHandle().startSystemMove()` and `startSystemResize()` to hand off control to the compositor, ensuring smooth movement that follows system security policies.

## Pinned Widget Resizing

- **The Issue:** Handling multi-edge resizing on Wayland while maintaining a fixed aspect ratio can lead to jittery window movement as the compositor and app fight over the window geometry.
- **Solution:** ShotX focuses resizing specifically on the **Bottom-Right Corner**. This provides the most stable and intuitive experience for proportional scaling. A visual handle (white dot) is provided to make this area discoverable.

## Pinned Widget Notifications (App Identity)

- **The Issue:** Notifications from the "Pin to Screen" feature may display 'Unknown' or 'python3' as the app name instead of 'ShotX'.
- **Root Cause:** GNOME Shell ignores the DBus Notify `app_name` field and resolves identity via the `desktop-entry` hint against installed `.desktop` files. If the app is run dynamically (e.g., via `uv run` in development), the `.desktop` file is not properly picked up by the notification daemon within the same session.
- **Future Resolution:** This is expected to be resolved when the app is statically packaged and installed (e.g., via `.deb`, `pip install` system-wide, or Flatpak), where the `.desktop` file is placed by the installer and the desktop database is refreshed before the first launch.
