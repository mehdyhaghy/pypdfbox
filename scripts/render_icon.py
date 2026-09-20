"""Regenerate the raster icon set from ``docs/assets/pypdfbox-icon.svg``.

Run after editing the SVG::

    .venv/bin/python scripts/render_icon.py

Rasterising uses skia-python (already a runtime dependency) so no extra
tooling is needed, and Pillow (likewise) assembles the multi-size Windows
``.ico``. The generated files are committed so neither installing nor
building pypdfbox ever has to rasterise anything.

Two margins, because the same mark has two jobs:

* **Application icon** -- the dock, the task switcher and the title bar all
  draw the bitmap edge to edge, and every platform's own icons leave a
  little air around the artwork. A tight render looks oversized next to
  them, so the package icons get a margin.
* **README / PyPI logo** -- GitHub paints ``#f6f8fa`` behind images in a
  rendered README, so any transparent padding baked into the PNG shows up
  as a grey band around the mark. That is what made the logo look like it
  was floating in an arbitrary grey box. The doc render is therefore
  flush: the mark fills the frame and GitHub's tile hugs it.
"""

import io
import pathlib

import skia
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
SVG = ROOT / "docs" / "assets" / "pypdfbox-icon.svg"
# Shipped inside the package: the debugger loads these at runtime.
PKG_ICON_DIR = ROOT / "pypdfbox" / "resources" / "icon"
# Documentation-only renders (README / GitHub / PyPI).
DOC_ICON_DIR = ROOT / "docs" / "assets"

PNG_SIZES = (16, 32, 48, 64, 128, 256, 512)
ICO_SIZES = (16, 32, 48, 64, 128, 256)

# Fraction of the canvas left empty on each side of the application icon.
APP_ICON_MARGIN = 0.07


def _render(size: int) -> Image.Image:
    """Rasterise the SVG flush into a square RGBA image of ``size`` pixels."""
    stream = skia.FILEStream(str(SVG))
    dom = skia.SVGDOM.MakeFromStream(stream)
    if dom is None:
        raise RuntimeError(f"could not parse {SVG}")
    dom.setContainerSize(skia.Size(size, size))
    surface = skia.Surface(size, size)
    with surface as canvas:
        dom.render(canvas)
    data = surface.makeImageSnapshot().encodeToData(skia.EncodedImageFormat.kPNG, 100)
    if data is None:
        raise RuntimeError(f"PNG encode failed at {size}px")
    return Image.open(io.BytesIO(bytes(data))).convert("RGBA")


def render_png(size: int, margin: float = 0.0) -> bytes:
    """Rasterise the SVG into a square RGBA PNG, inset by ``margin``.

    ``margin`` is a fraction of the canvas per side, so 0.07 leaves 7% air
    on every edge. The mark is rendered at the inner size and centred,
    which keeps it pixel-sharp rather than scaling an already-rasterised
    image down.
    """
    if margin <= 0:
        image = _render(size)
    else:
        inner = max(1, round(size * (1 - 2 * margin)))
        image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        offset = (size - inner) // 2
        image.paste(_render(inner), (offset, offset))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def main() -> None:
    PKG_ICON_DIR.mkdir(parents=True, exist_ok=True)
    DOC_ICON_DIR.mkdir(parents=True, exist_ok=True)

    for size in PNG_SIZES:
        png = render_png(size, margin=APP_ICON_MARGIN)
        (PKG_ICON_DIR / f"pypdfbox-{size}.png").write_bytes(png)
        print(f"  wrote pypdfbox-{size}.png ({len(png)} bytes)")

    # Windows .ico for Tk's iconbitmap. Pillow's ICO writer downsamples a
    # SINGLE source image to each requested size and silently drops any size
    # larger than that source -- so it must be seeded with the LARGEST entry
    # (256 is the ICO format's maximum), not the smallest.
    with Image.open(PKG_ICON_DIR / "pypdfbox-256.png") as source:
        source.convert("RGBA").save(
            PKG_ICON_DIR / "pypdfbox.ico",
            format="ICO",
            sizes=[(s, s) for s in ICO_SIZES],
        )
    print(f"  wrote pypdfbox.ico ({len(ICO_SIZES)} sizes)")

    # README / PyPI logo. PyPI's renderer does not display SVG, so the
    # README must point at a PNG for the image to appear on the project page.
    # Rendered flush -- see the module docstring.
    (DOC_ICON_DIR / "pypdfbox-logo.png").write_bytes(render_png(512))
    print("  wrote docs/assets/pypdfbox-logo.png")


if __name__ == "__main__":
    main()
