---
title: Image Editor — Crop, Resize & Effects
description: Edit your screenshots with a lightweight, built-in editor featuring cropping, resizing, and various visual effects.
---

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

| Action         | Control                                         |
| -------------- | ----------------------------------------------- |
| Zoom In        | ++ctrl+equal++ or ++ctrl+scroll-up++            |
| Zoom Out       | ++ctrl+minus++ or ++ctrl+scroll-down++          |
| Reset Zoom     | ++ctrl+0++ or click the zoom % label            |
| Pan            | Hold ++space++ and drag                         |
| Undo           | ++ctrl+z++                                      |
| Redo           | ++ctrl+y++                                      |
| Copy to Clipboard | ++ctrl+c++                                   |
| Save As        | ++ctrl+s++                                      |
| Open File      | ++ctrl+o++                                      |

## Keyboard Tool Shortcuts

All annotation tools are accessible via single-key shortcuts. Hover over any tool button to see its shortcut hint.

| Key   | Tool        |
| ----- | ----------- |
| ++v++ | Select/Move |
| ++r++ | Rectangle   |
| ++e++ | Ellipse     |
| ++a++ | Arrow       |
| ++t++ | Text        |
| ++f++ | Freehand    |
| ++c++ | Crop        |
| ++b++ | Blur        |
| ++h++ | Highlight   |
| ++s++ | Step Number |
| ++x++ | Eraser      |

See [Annotation Tools](annotation.md) for full tool reference.

## Crop & Resize

### Cropping

1. Press ++c++ or select the Crop tool from the toolbar
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
