# Settings Reference

ShotX stores configuration in `~/.config/shotx/settings.yaml`. Settings can be edited via the Settings dialog in the Main Window or directly in the YAML file.

## Capture Settings

```yaml
capture:
    output_dir: ~/Pictures/ShotX # Where screenshots are saved
    filename_pattern: "ShotX_{datetime}" # Filename template
    image_format: png # png, jpg, jpeg, webp
    jpeg_quality: 95 # Quality for JPEG/WebP (1-100)
    screenshot_delay: 0 # Seconds to wait before capture
    show_cursor: false # Include cursor in screenshots
    auto_detect_regions: true # Auto-detect windows/widgets
    after_capture_action: annotate # annotate, save, capture
    show_notification: true # Show desktop notification
    last_annotation_color: "#FF0000" # Last used annotation color
    video_fps: 30 # Recording frame rate
    capture_audio: false # Record system audio
```

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
    save_to_file: true # Save screenshot to disk
    copy_to_clipboard: true # Copy image to clipboard
    upload_image: false # Upload to configured destination
    open_in_editor: false # Open in image editor after capture
```

## Upload Settings

```yaml
upload:
    default_uploader: tmpfiles # imgur, imgbb, tmpfiles, s3, ftp, sftp, custom:name
    copy_url_to_clipboard: true # Copy upload URL after upload

    imgur:
        client_id: ""
        access_token: ""

    imgbb:
        api_key: ""

    s3:
        endpoint_url: "" # Leave empty for AWS
        access_key: ""
        secret_key: ""
        bucket_name: ""
        public_url_format: ""

    ftp:
        host: ""
        port: 21
        username: ""
        password: ""
        remote_path: /
        public_url_format: ""

    sftp:
        host: ""
        port: 22
        username: ""
        password: ""
        remote_path: /
        public_url_format: ""

    shortener:
        enabled: false
        provider: tinyurl # Shortener service provider
```

## Hotkey Settings

```yaml
hotkeys:
    capture_fullscreen: "" # e.g. "Print"
    capture_region: "Alt+Shift+X"
    capture_window: ""
    capture_ocr: ""
    capture_color_picker: "Alt+Shift+Q"
    capture_ruler: ""
    capture_qr_scan: ""
    pin_region: ""
```

See [Hotkeys](hotkeys.md) for details on configuring keyboard shortcuts.
