# Image Editor

ShotX includes a full-featured image editor with annotation tools, effects, beautification, and image combining.

## Opening the Editor

```bash
# Open empty editor
shotx --edit

# Edit a specific image
shotx --edit /path/to/image.png
```

Or from the Main Window: Sidebar → Tools → Image Editor.

## Canvas Controls

| Action        | Control                           |
| ------------- | --------------------------------- |
| Zoom In       | ++ctrl+"+"++ or scroll up         |
| Zoom Out      | ++ctrl+"-"++ or scroll down       |
| Fit to Window | ++ctrl+0++                        |
| Pan           | Hold middle mouse button and drag |

## Annotation Tools

All annotation tools from the capture overlay are available. See [Annotation Tools](annotation.md) for the full reference.

## Crop & Resize

### Cropping

1. Select the Crop tool
2. Drag to define the crop area
3. Adjust using interactive corner/edge handles
4. Confirm with ++enter++

### Resizing

Resize the image by percentage or exact pixel dimensions with aspect ratio lock.

## Effects

### Borders

Add solid or styled borders around the image with configurable width and color.

### Shadows

Apply drop shadows with configurable offset, blur radius, and color.

### Watermarks

Overlay text or image watermarks with configurable position, opacity, and size.

## Beautifier

Transform screenshots into presentation-ready images:

- **Rounded Corners**: Configurable radius
- **Gradient Backgrounds**: Multiple color presets
- **Drop Shadow**: Soft shadow beneath the image
- **Padding**: Adjustable spacing around the image

## Image Combiner

Combine multiple images into a single output:

- **Horizontal stacking**: Side-by-side layout
- **Vertical stacking**: Top-to-bottom layout
- **Configurable spacing**: Gap between images
- **Alignment options**: Top/center/bottom (horizontal), left/center/right (vertical)
