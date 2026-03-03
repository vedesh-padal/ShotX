# Image Effects

The Image Effects dialog provides users with basic image beautification parameters including frames, background padding, shadows, and text watermarking.

## Core Mechanics

When an effect is applied via the "✨ Effects..." toolbar button inside the Image Editor, it acts as a **destructive flattening operation** on the current canvas state.

1.  **Canvas Rasterization:** All independent vector items (Text, Arrows, Rectangles, Freehand) currently drawn on the canvas are temporarily mapped onto a flat 32-bit `QImage`.
2.  **Dimension Expansion:** The application math dynamically calculates the necessary new dimensions of the image canvas required to securely fit any applied `Padding`, `Border Width`, and the maximum mathematical outer bounding box required by the `Shadow Radius` and its specific `[X, Y]` directional offsets.
3.  **Layer Composite Rendering:**
    - The new expanded canvas is completely filled with the designated `Background Color` (or transparent if omitted).
    - A native `QGraphicsDropShadowEffect` is applied to a temporary off-screen `QGraphicsPixmapItem` buffer containing the flattened pre-effects image.
    - The scene renders the casted shadow directly into the expanded background, followed by the padded image itself.
    - Any selected Border is drawn directly onto the image's inner edge footprint.
    - The Watermark overlay is painted as the absolute top-level object on the composite with the user's requested opacity.
4.  **Scene Replacement and Undo Stack:** Once flattened, all physical vector objects from the scene are scrubbed. The active Image view is completely swapped out for this new final master image.
    - Because this uses `QUndoCommand`, pressing `Ctrl+Z` reverses the operation instantly: The old untouched original image is restored, and all vectors mapped to it are repopulated identically back into their independent movable states.

## Border & Shadow Features

- **Border Width & Color:** Adds an even solid-color stroke wrapping directly inside the edge-boundary of the original screenshot.
- **Background Padding:** Adds an even transparent or solid-color spacer between the image/border and the final edge of the file.
- **Background Color:** The color of the padding layer.
- **Drop Shadow:** Uses high-quality variable-radius blur logic from Qt.
    - **Radius:** Controls the softness/spread of the shadow.
    - **Offset X/Y:** Controls the directional light-casting of the shadow independently.

## Watermark Features

- **Custom Text:** An arbitrary watermark string.
- **Opacity:** A `0.0` (invisible) to `1.0` (solid) alpha scale dictating transparency.
- **Position:** Provides snap locations:
    - `Bottom Right`
    - `Bottom Left`
    - `Top Right`
    - `Top Left`
    - `Center`
    - `Tiled Grid`: Specifically repeats the text infinitely across the entire expanded dimensions of the new canvas, leaving ~50 pixels of safe spacing between each word vertically and horizontally.
