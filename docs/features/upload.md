---
title: Upload Engine — Imgur, S3, FTP & Custom
description: Configure ShotX to automatically upload your captures to Imgur, S3, FTP, or your own custom uploader.
---

# Upload Engine

ShotX supports uploading screenshots and files to multiple destinations. Uploads run in the background with progress notifications.

## Built-in Uploaders

### tmpfiles.org (Default)

Free, anonymous file hosting. No API key required. Files expire after a set period.

### Imgur

Upload images to Imgur. Requires a Client ID (free API registration).

**Setup:** Settings → Upload → Imgur → Client ID

### ImgBB

Upload images to ImgBB. Requires an API key.

**Setup:** Settings → Upload → ImgBB → API Key

## Cloud Uploaders

### Amazon S3 / S3-Compatible

Works with AWS S3, Backblaze B2, MinIO, DigitalOcean Spaces, Cloudflare R2, and any S3-compatible service.

**Configuration:**

| Setting           | Description                           |
| ----------------- | ------------------------------------- |
| Endpoint URL      | Custom endpoint (leave empty for AWS) |
| Access Key        | S3 access key ID                      |
| Secret Key        | S3 secret access key                  |
| Bucket Name       | Target bucket                         |
| Public URL Format | Template for constructing public URLs |

### FTP / SFTP

Upload via FTP or SFTP (SSH File Transfer Protocol).

**Configuration:**

| Setting           | Description                           |
| ----------------- | ------------------------------------- |
| Host              | Server hostname                       |
| Port              | Server port (21 for FTP, 22 for SFTP) |
| Username          | Login username                        |
| Password          | Login password                        |
| Remote Path       | Upload directory on server            |
| Public URL Format | Template for constructing public URLs |

## Custom Uploaders (.sxcu)

ShotX supports ShareX's `.sxcu` custom uploader format. Place `.sxcu` files in `~/.config/shotx/uploaders/`.

See [Custom Uploaders Guide](../configuration/custom-uploaders.md) for details.

## URL Shortener

After upload, URLs can be automatically shortened. Configurable via Settings → Upload → URL Shortener.

### CLI Usage

```bash
# Shorten a specific URL
shotx --shorten-url "https://example.com/very/long/path"

# Shorten clipboard contents
shotx --shorten-url
```

## Selecting the Upload Destination

- **Main Window:** Sidebar → Destinations → select uploader
- **Settings:** Settings → Upload → Default Uploader
- **Config:** `settings.yaml` → `upload.default_uploader`
