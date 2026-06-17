# pypdfbox.rendering — rasterising PDF pages

`PDFRenderer` renders a page to a PIL `Image.Image` (or directly to a
file-like via the `RenderDestination`). The implementation is a
content-stream consumer (`PageDrawer` extends `PDFGraphicsStreamEngine`)
that drives [skia-python](https://kyamagu.github.io/skia-python/) as the
2-D backend. The skia backend is Apache-2.0-compatible (BSD), satisfying
the project's permissive-license rule.

## Public surface

| Class | Purpose |
| --- | --- |
| `PDFRenderer` | The renderer. Holds a `PDDocument`, a `GlyphCache`, and a `ResourceCache`. `render_image(page_index, scale=1.0, image_type=ImageType.RGB) -> Image`, `render_image_with_dpi(page_index, dpi)`, `render_page_to_graphics(page_index, graphics)`. |
| `PageDrawer` | The content-stream consumer subclass of `PDFGraphicsStreamEngine` that issues skia paint calls. Override per-callback to instrument painting. |
| `PageDrawerParameters` | Construction-time configuration: page, image type, sub-sampling, annotation rendering, optional content. |
| `RenderDestination` | `enum.Enum` — `EXPORT` (default), `VIEW`, `PRINT`. Influences ExtGState dispatch (rendering intent, smoothness). |
| `ImageType` | `enum.Enum` — `BINARY`, `GRAY`, `RGB`, `ARGB`. Map to PIL modes `1`/`L`/`RGB`/`RGBA`. |
| `GlyphCache` | Per-font path cache. Lazily computes outlines via `FontBoxFont.get_path(name)`. Threadsafe via per-font lock. |
| `GroupGraphics` | Implements an off-screen transparency-group buffer. Used by both soft masks and `q ... /Form Do ... Q` when the form X-object carries a `/Group` dictionary. |
| `TransparencyGroup` | One off-screen group + its bounds. Composited back into the parent on `Q`. Implements isolated/knockout/non-isolated semantics. |
| `SoftMask` | Wraps a `/SMask` dictionary and produces a per-pixel alpha mask. Type "Alpha" and "Luminosity" are both supported. |
| `SoftPaintContext` | Skia paint adapter that consumes a `SoftMask`. |
| `TilingPaint` | Skia `Shader` for tiling patterns (`/PatternType 1`). |
| `TilingPaintFactory` / `TilingPaintParameter` | Tiling-paint construction + caching. |

## Typical usage

```python
from pypdfbox import Loader
from pypdfbox.rendering import PDFRenderer, ImageType

with Loader.load_pdf("in.pdf") as doc:
    renderer = PDFRenderer(doc)
    img = renderer.render_image_with_dpi(0, 144, image_type=ImageType.RGB)
    img.save("page0.png")
```

## Type-3 fonts

When the engine encounters a Type-3 glyph, `PageDrawer.render_type3_glyph`
spawns a new `PDFGraphicsStreamEngine` whose output is captured into a
glyph-local cache (`GlyphCache.get_type3_glyph`). The captured path is
then painted at the parent text-state CTM.

## Soft mask + transparency group composition

The off-screen flow for a transparency group is:

1. `q ... /Form Do ... Q` is encountered.
2. `PageDrawer` allocates a `TransparencyGroup` (off-screen Skia surface)
   using bounds from the form X-object's `/BBox` mapped through the CTM.
3. The form X-object's content stream is processed against the off-screen
   surface.
4. On `Q`, the group is composited back. Group `/I` (isolated) and `/K`
   (knockout) flags select non-isolated/isolated and additive/replace
   composition respectively.

Soft masks intercept the group's alpha and replace it with the rendered
mask's alpha (or luminosity), then the result is composited.

## Skia backend notes

- `skia-python` ships pre-built wheels for the OS/CPU combinations
  pypdfbox supports.
- Skia uses RGBA-premultiplied internally; pypdfbox converts to/from
  straight-alpha at the boundary.
- The renderer holds no global Skia surface — every `render_image` call
  allocates its own. Render in parallel by giving each thread its own
  `PDFRenderer`.

## PDFBox divergence

- `PDFRenderer.renderImage(int pageIndex, float scale, ImageType type)` →
  `render_image(page_index, scale=1.0, image_type=ImageType.RGB)`. The
  return type is `PIL.Image.Image` rather than Java `BufferedImage`.
- `PDFRenderer.renderImageWithDPI(int pageIndex, int dpi)` →
  `render_image_with_dpi(page_index, dpi)`. `dpi` is an `int` or `float`.
- `PageDrawer.drawPage(Graphics, PDPage)` becomes
  `draw_page(graphics, page)`; the `graphics` argument is a Skia
  `Canvas`.
- `ImageType.RGB` always produces RGB (no alpha). Use `ImageType.ARGB`
  for transparent backgrounds.

## See also

- [pdmodel-graphics.md](pdmodel-graphics.md) — color spaces + shadings
  feed into the renderer.
- [pdmodel-font.md](pdmodel-font.md) — glyph paths come from here.
- [contentstream.md](contentstream.md) — the operator dispatch the
  renderer hooks into.
- [guides/rendering.md](../guides/rendering.md) — DPI selection,
  multi-threading.
