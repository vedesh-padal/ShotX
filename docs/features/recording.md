# Screen Recording

ShotX can record any screen region as **MP4** or **GIF**.

## Usage

### From Tray Menu

1. Right-click tray icon → **Record** → **Record MP4** or **Record GIF**
2. Select the recording region using the overlay
3. Recording starts immediately
4. Click **Stop Recording** in the tray menu to finish

### From CLI

Screen recording is currently available via the tray menu and Main Window only.

## Output Formats

### MP4 (Video)

Records directly to MP4. Audio capture is supported when enabled in settings.

### GIF (Animated)

Records as MP4 first, then post-processes with FFmpeg using the `palettegen` + `paletteuse` filter chain for high-quality, optimized GIFs.

## Backends

| Display Server    | Backend             | Package       |
| ----------------- | ------------------- | ------------- |
| X11               | `ffmpeg -f x11grab` | `ffmpeg`      |
| Wayland (wlroots) | `wf-recorder`       | `wf-recorder` |
| Wayland (GNOME)   | Not yet supported   | —             |

!!! warning "GNOME Wayland"
GNOME Wayland does not support `wf-recorder` (it relies on `wlr-screencopy` which GNOME refuses to implement). The only option is the XDG Desktop Portal + PipeWire, which forces a security popup on every recording. This is planned for a future release.

    For now, GNOME Wayland users can use GNOME's built-in recorder (++ctrl+shift+alt+r++) or switch to an X11 session.

## Settings

| Setting          | Description                                      |
| ---------------- | ------------------------------------------------ |
| Video FPS        | Recording frame rate (default: 30)               |
| Capture Audio    | Record system audio via PulseAudio/PipeWire      |
| Output Directory | Where recordings are saved                       |
| Filename Pattern | Naming pattern with `{datetime}`, `{type}`, etc. |
