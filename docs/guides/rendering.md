# Rendering

Pypdfbox renders pages through [`PDFRenderer`](../api/rendering.md), a
port of `org.apache.pdfbox.rendering.PDFRenderer`. The output is a
[Pillow](https://python-pillow.org/) `Image.Image`, so callers can
save in any format Pillow supports.

## Render a page to a Pillow image

```python
from pypdfbox.pdmodel import PDDocument
from pypdfbox.rendering import PDFRenderer

with PDDocument.load("input.pdf") as doc:
    renderer = PDFRenderer(doc)
    img = renderer.render_image_with_dpi(0, dpi=144.0)
    img.save("page1.png")
```

`render_image_with_dpi` takes the page index (0-based) and a DPI
value; the page's media-box is scaled by `dpi / 72`. A `render_image`
overload accepts a unitless scale factor (1.0 == 72 DPI) for parity
with upstream PDFBox.

## Choose an ImageType

`ImageType` mirrors upstream's `org.apache.pdfbox.rendering.ImageType`.
Passing the enum sets Pillow's mode for the returned image.

```python
from pypdfbox.rendering import PDFRenderer
from pypdfbox.rendering.image_type import ImageType

with PDDocument.load("input.pdf") as doc:
    renderer = PDFRenderer(doc)
    rgb = renderer.render_image_with_dpi(0, dpi=144.0, image_type=ImageType.RGB)
    gray = renderer.render_image_with_dpi(0, dpi=144.0, image_type=ImageType.GRAY)
    binary = renderer.render_image_with_dpi(0, dpi=144.0, image_type=ImageType.BINARY)
    argb = renderer.render_image_with_dpi(0, dpi=144.0, image_type=ImageType.ARGB)
```

Mappings to Pillow modes:

| ImageType | Pillow mode |
|---|---|
| `BINARY` | `"1"` |
| `GRAY` | `"L"` |
| `RGB` / `BGR` | `"RGB"` |
| `ARGB` | `"RGBA"` |

`ImageType.to_buffered_image_type()` still returns the matching
Java AWT `BufferedImage.TYPE_*` integer in case a downstream
porting layer relies on it.

## Apply a RenderDestination

Optional-content groups can hide or show based on the render purpose
(view, print, export). Pass the destination per-call or set a default
on the renderer:

```python
from pypdfbox.rendering.render_destination import RenderDestination

renderer.set_default_destination(RenderDestination.PRINT)
img = renderer.render_image_with_dpi(0, dpi=300.0)

# Or override for a single call:
export = renderer.render_image_with_dpi(
    0, dpi=144.0, destination=RenderDestination.EXPORT
)
```

Bare strings (`"View"`, `"Print"`, `"Export"`) are also accepted for
the per-call argument.

## Subclass `PageDrawer`

For custom painting (debug overlays, region inspection, font
fallbacks), subclass `PageDrawer` and inject it via the renderer's
factory hook. The canonical example lives at
[`pypdfbox/examples/rendering/custom_page_drawer.py`](https://github.com/Mehdy-haghy/pypdfbox/blob/main/pypdfbox/examples/rendering/custom_page_drawer.py).
A `custom_graphics_stream_engine.py` in the same directory shows how
to override stream parsing without going through the full drawer
plumbing.

```python
from pypdfbox.rendering import PDFRenderer
from pypdfbox.rendering.page_drawer import PageDrawer


class HighlightDrawer(PageDrawer):
    def show_text(self, string):
        # Intercept text show operations here.
        super().show_text(string)


class HighlightRenderer(PDFRenderer):
    def create_page_drawer(self, parameters):
        return HighlightDrawer(parameters)


with PDDocument.load("input.pdf") as doc:
    HighlightRenderer(doc).render_image_with_dpi(0, dpi=144.0).save("out.png")
```

## Color rendering intent

The PDF `ri` operator selects how out-of-gamut colors are mapped to
the output device. The renderer honours all four ISO 32000-1 values
(`AbsoluteColorimetric`, `RelativeColorimetric`, `Saturation`,
`Perceptual`) — they are picked up from the content stream directly,
no API call needed. Author-side, write the intent through
`PDPageContentStream`:

```python
from pypdfbox.pdmodel import PDPage, PDDocument
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream

doc = PDDocument()
page = PDPage()
doc.add_page(page)
with PDPageContentStream(doc, page) as cs:
    cs.set_rendering_intent("Perceptual")
    # ... draw operations
```

## Glyph coverage limits

The lite renderer relies on the bundled standard-14 font metrics for
glyph shapes. Symbol and ZapfDingbats coverage is partial: glyphs
outside the standard PostScript name list draw as a placeholder box
and a warning is logged once per missing name. For full coverage,
embed a TrueType or OpenType font in the PDF — the renderer reads
embedded font programs directly.

## Backend characteristics

Pypdfbox renders with a Pillow + skia-python fallback. The pixel
output is not bit-identical to Java PDFBox's `Graphics2D`-based
rasteriser, primarily because of anti-aliasing differences and
subpixel positioning. Concretely:

- Edge anti-aliasing falls back to a Pillow `LANCZOS` downsample
  when skia-python is unavailable.
- Text hinting differs from FreeType-on-Java because skia does its
  own glyph rasterisation.
- Knockout/transparency groups blend in sRGB; upstream uses the
  ICC profile of the destination buffer when present.

Compare structurally — extracted text, page count, content-stream
operator parity, OCR-on-rendered-image text — rather than relying
on pixel-exact diffs against upstream output.

## See also

- [Examples: `pypdfbox/examples/rendering/`](https://github.com/Mehdy-haghy/pypdfbox/tree/main/pypdfbox/examples/rendering)
- [API reference: `pypdfbox.rendering`](../api/rendering.md)
- [Documentation index](../index.md)
