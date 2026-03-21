---
title: Image Combiner — Join Multiple Shots
description: Quickly merge multiple screenshots into a single image, either vertically or horizontally.
---

# Image Combiner

The Image Combiner tool allows users to mechanically append a secondary image file onto the boundaries of their current Image Editor canvas.

## Core Mechanics

When the "🔗 Combine..." tool is invoked and a secondary file (`Image 2`) is picked from disk, ShotX performs a complex spatial calculation to build a merged canvas.

1.  **Canvas Rasterization:** The current Image Editor scene (known as `Image 1`), including all drawn vector primitives, is rasterized into a flat, transparent `QImage` buffer.
2.  **File Input Loading:** `Image 2` is buffered into a `QImage` off the hard drive.
3.  **Dimension Calculation & Spatial Grid:**
    - Based on the `Orientation` (Horizontal Side-by-Side vs Vertical Stacked), the tool calculates the ultimate geometric limits required to fit both images.
    - Instead of simply snapping to `(0,0)`, the script analyzes aspect ratio mismatches. If `Horizontal` orientation is chosen but the heights differ, the `Orthogonal Alignment` dictates mapping:
        - `Start`: Pinned to Y=0 (Top)
        - `Center`: Mismatched image vertically centered via `(Total Height - Local Height) // 2`
        - `End`: Pinned to maximum Y (Bottom).
    - The `Gap Spacing` injects a mathematical block of empty space directly between the two inner coordinates.
4.  **Background Fill & Assembly:**
    - A master `QImage` canvas matching the calculated `Total Width` and `Total Height` is created.
    - It is completely flooded with the user's `Background Fill` color selection, replacing all transparent dead space caused by spacing gaps and alignment offsets.
    - `Image 1` and `Image 2` are cleanly painted atop the background at their calculated X/Y destination coordinates.
5.  **Undo Registration:** The process flattens the result down to the main `pixmap` layer, appending the original components into the `CombineCommand` payload. Hitting `Ctrl+Z` detaches the combined structure, seamlessly reverting to the original size and restoring the independent manipulatable state of `Image 1`'s vectors.

## Features

- **Orientation (Axis):** Append on X axis (`Horizontal Side-by-side`) or Y axis (`Vertical Stacked`).
- **Orthogonal Alignment:** Handle size discrepancies by shifting the shorter image to the `Center`, `Start` (Top/Left), or `End` (Bottom/Right) boundary.
- **Gap Spacing:** Inject padding pixels exclusively _between_ the two appended images.
- **Background Fill:** The uniform `QColor` solid fill used to paint underneath the images, effectively styling the Gap Spacing and Orthogonal dead zones.
