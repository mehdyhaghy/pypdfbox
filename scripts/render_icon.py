"""Regenerate the raster icon set from ``docs/assets/pypdfbox-icon.svg``.

Run after editing the SVG::

    .venv/bin/python scripts/render_icon.py

Rasterising uses skia-python (already a runtime dependency) so no extra
tooling is needed, and Pillow (likewise) assembles the multi-size Windows
``.ico``. The generated files are committed so neither installing nor
building pypdfbox ever has to rasterise anything.
"""

from __future__ import annotations

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


def render_png(size: int) -> bytes:
    """Rasterise the SVG into a square RGBA PNG of ``size`` pixels."""
    stream = skia.FILEStream(str(SVG))
    dom = skia.SVGDOM.MakeFromStream(stream)
    if dom is None:
        raise RuntimeError(f"could not parse {SVG}")
    dom.setContainerSize(skia.Size(size, size))
    surface = skia.Surface(size, size)
    with surface as canvas:
        dom.render(canvas)
    image = surface.makeImageSnapshot()
    data = image.encodeToData(skia.EncodedImageFormat.kPNG, 100)
    if data is None:
        raise RuntimeError(f"PNG encode failed at {size}px")
    return bytes(data)


def main() -> None:
    PKG_ICON_DIR.mkdir(parents=True, exist_ok=True)
    DOC_ICON_DIR.mkdir(parents=True, exist_ok=True)

    for size in PNG_SIZES:
        png = render_png(size)
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
    (DOC_ICON_DIR / "pypdfbox-logo.png").write_bytes(render_png(256))
    print("  wrote docs/assets/pypdfbox-logo.png")


if __name__ == "__main__":
    main()
