---
title: Settings Reference — Configure Your Experience
description: Detailed reference for all ShotX settings, from capture behavior and file naming to automated workflows.
---

# Settings Reference

ShotX stores configuration in `~/.config/shotx/settings.yaml`. Settings can be edited via the Settings dialog in the Main Window or directly in the YAML file.

!!! note
    Manual changes to `settings.yaml` require an app restart to take effect if changed while the app is running.

## Capture Settings

```yaml
capture:
    output_dir: ~/Pictures/ShotX   # Where screenshots are saved
    filename_pattern: "ShotX_{date}_{time}"  # Filename template
    image_format: png              # png, jpg, jpeg, webp
    jpeg_quality: 95               # Quality for JPEG/WebP (1-100)
    screenshot_delay: 0            # Seconds to wait before capture
    show_cursor: false             # Include cursor in screenshots
    auto_detect_regions: true      # Auto-detect windows/widgets
    after_capture_action: edit     # "edit" (annotate first) or "save" (save immediately)
    show_notification: true        # Show desktop notification after capture
    play_sound: false              # Play a shutter sound on capture
    last_annotation_color: "#ff0000"  # Last used annotation color (persisted)
    video_fps: 30                  # Recording frame rate
    capture_audio: false           # Record system audio
```

!!! note
    `after_capture_action: edit` opens the annotation overlay before saving. `save` saves the screenshot immediately without annotation.

## Filename Pattern Variables

| Variable      | Example Output                      |
| ------------- | ----------------------------------- |
| `{date}`      | `2026-03-05`                        |
| `{time}`      | `14-30-45`                          |
| `{datetime}`  | `2026-03-05_14-30-45`               |
| `{type}`      | `fullscreen`, `region`, `recording` |
| `{counter}`   | `0001`                              |
| `{timestamp}` | `1772885445`                        |

## Workflow Settings

```yaml
workflow:
    save_to_file: true       # Save screenshot to disk
    copy_to_clipboard: true  # Copy image to clipboard
    upload_image: false      # Upload to configured destination
    open_in_editor: false    # Open in image editor after capture
```

## Upload Settings

```yaml
upload:
    enabled: false
    default_uploader: tmpfiles  # imgur, imgbb, tmpfiles, s3, ftp, sftp, custom:name
    copy_url_to_clipboard: true # Copy upload URL after upload

    imgur:
        client_id: ""
        access_token: ""

    imgbb:
        api_key: ""

    s3:
        endpoint_url: ""  # Leave empty for AWS
        access_key: ""
        secret_key: ""
        bucket_name: ""
        public_url_format: ""

    ftp:
        host: ""
        port: 21
        username: ""
        password: ""
        remote_dir: /              # Upload directory on server
        public_url_format: ""

    sftp:
        host: ""
        port: 22
        username: ""
        password: ""
        key_file: ""               # Path to SSH private key (optional)
        remote_dir: /              # Upload directory on server
        public_url_format: ""

    shortener:
        enabled: false
        provider: tinyurl  # tinyurl, isgd, vgd
```

## Hotkey Settings

```yaml
hotkeys:
    capture_fullscreen: ""         # e.g. "Print"
    capture_region: "Alt+Shift+X"
    capture_window: ""
    capture_ocr: ""
    capture_color_picker: "Alt+Shift+Q"
    capture_ruler: ""
    capture_qr_scan: ""
    pin_region: ""
```

See [Hotkeys](hotkeys.md) for details on configuring keyboard shortcuts.
