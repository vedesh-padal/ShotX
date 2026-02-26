# Image Beautifier

The Image Beautifier is a one-click macro tool designed to generate modern, aesthetic "macOS-style" screenshot presentations without requiring manual layer configuration.

## Core Mechanics

When the "🪄 Beautify..." tool is applied, it transforms the active canvas into a padded presentation frame through a destructive flattening operation (fully reversible via `Ctrl+Z` Undo history).

1.  **Canvas Rasterization:** All active vectors and base pixels are merged into a single flat `QImage` layer.
2.  **Corner Clipping (Masking):**
    - A new temporary `QImage` layer is constructed.
    - A mathematical `QPainterPath` is generated utilizing `addRoundedRect` using the user's `Corner Radius` parameter.
    - The flat source image is drawn _through_ this clipping path, smoothly masking off the original sharp corners, leaving transparent pixels and anti-aliased curved edges.
3.  **Dimension Expansion & Gradients:**
    - The target output dimensions are calculated by adding the `Background Padding` on all four edges.
    - A master background `QImage` canvas is spawned.
    - A high-quality `QLinearGradient` (or solid transparent brush) is painted across this master canvas. Hardcoded gradient presets (e.g., Sunset, Ocean, Mojave, Purple Pink) construct color interpolation logic stretching from `0.0` at the top-left to `1.0` at the bottom-right.
4.  **Shadow Effects & Compositing:**
    - A native `QGraphicsDropShadowEffect` is applied to the clipped inner image via a temporary `QGraphicsScene`. The shadow radius dynamically scales based on the image size to prevent excessive bleeding on small snips, and offsets itself downwards.
    - The inner image, carrying its drop shadow, is rendered exactly into the center of the padded gradient master canvas.
5.  **Scene Replacement:** The active Image Editor canvas resets to exactly wrap this newly generated `QImage`, wiping out the original image dimensions and replacing the base `pixmap`.

## Features

- **Background Styles:** A selection of curated vibrant CSS-like gradient palettes (`Sunset`, `Ocean`, `Purple Pink`, `Mojave`), alongside neutral `Solid White`, `Dark Chrome`, and natively `Transparent`.
- **Background Padding:** An expansion factor extending the total dimensions of the output file around the image (20px - 500px).
- **Window Corner Radius:** The sharpness of the inner image mask (0px up to fully rounded circles).
