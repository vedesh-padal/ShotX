# Custom Uploaders (.sxcu)

ShotX supports ShareX's `.sxcu` custom uploader format, allowing you to upload to any HTTP-based file hosting service.

## Setup

Place `.sxcu` files in `~/.config/shotx/uploaders/`.

Then set the default uploader to `custom:<name>` (without the `.sxcu` extension):

```yaml
upload:
    default_uploader: "custom:my_uploader"
```

## .sxcu Format

An `.sxcu` file is a JSON file with the following structure:

```json
{
    "Name": "My Uploader",
    "DestinationType": "ImageUploader",
    "RequestMethod": "POST",
    "RequestURL": "https://api.example.com/upload",
    "Headers": {
        "Authorization": "Bearer YOUR_API_KEY"
    },
    "Body": "MultipartFormData",
    "FileFormName": "file",
    "URL": "{json:data.url}",
    "ThumbnailURL": "{json:data.thumb}",
    "DeletionURL": "{json:data.delete_url}"
}
```

## Fields

| Field           | Required | Description                                    |
| --------------- | -------- | ---------------------------------------------- |
| `Name`          | Yes      | Display name                                   |
| `RequestURL`    | Yes      | Upload endpoint URL                            |
| `RequestMethod` | No       | HTTP method (default: `POST`)                  |
| `Headers`       | No       | HTTP headers (key-value pairs)                 |
| `Body`          | No       | Body type: `MultipartFormData` or `JSON`       |
| `FileFormName`  | No       | Form field name for the file (default: `file`) |
| `URL`           | Yes      | Response parsing pattern for the URL           |
| `ThumbnailURL`  | No       | Response parsing pattern for thumbnail         |
| `DeletionURL`   | No       | Response parsing pattern for deletion URL      |

## Response Parsing

Use `{json:path.to.field}` syntax to extract values from JSON responses:

- `{json:url}` → root-level `url` field
- `{json:data.url}` → nested `data.url` field
- `{json:data.links.original}` → deeply nested field

## Finding .sxcu Files

Many services provide pre-made `.sxcu` files:

- [ShareX Custom Uploaders](https://getsharex.com/custom-uploaders/) — official ShareX repository
- GitHub — search for `.sxcu` files for your preferred hosting service

!!! note
ShotX aims for compatibility with the core ShareX `.sxcu` format. Some advanced ShareX-specific features (like conditional logic) may not be supported.
