"""
``pypdfbox imagetopdf -i img1 [img2 ...] -o out.pdf [-pageSize SIZE]
[-resize] [-orientation ORI]`` — build a PDF from one or more raster
images.

Mirrors upstream ``org.apache.pdfbox.tools.ImageToPDF``. Upstream loads
each image via ``PDImageXObject.createFromFileByExtension`` (delegating
to ``JPEGFactory`` / ``LosslessFactory``), creates one page per image,
and draws the image at ``(0, 0)`` either at its intrinsic pixel size or
stretched to the page when ``-resize`` is set.

pypdfbox doesn't yet ship the ``JPEGFactory`` / ``LosslessFactory``
helpers, so we build the Image XObject inline:

* ``.jpg`` / ``.jpeg`` payloads embed verbatim as ``/DCTDecode``.
* every other Pillow-readable format (PNG, TIFF, BMP, GIF, ...) is
  decoded to RGB pixels and stored as a FlateDecode-compressed raster.

Exit codes follow upstream:
  0  success
  4  I/O error (raised as ``OSError`` and caught by ``cli.run_cli``)
"""
from __future__ import annotations

import argparse
import zlib
from pathlib import Path
from typing import Iterable

from PIL import Image

from pypdfbox.cos import COSName, COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.graphics.image import PDImageXObject
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream

# ---------------------------------------------------------------------------
# page-size table (mirrors upstream ImageToPDF#createRectangle)
# ---------------------------------------------------------------------------

# Standard A-series sizes in PDF user-space points (1pt = 1/72 inch).
# Values match Apache PDFBox's PDRectangle constants.
_PAGE_SIZES: dict[str, PDRectangle] = {
    "letter": PDRectangle.LETTER,  # type: ignore[attr-defined]
    "legal": PDRectangle.LEGAL,  # type: ignore[attr-defined]
    "a0": PDRectangle(0.0, 0.0, 2384.0, 3370.0),
    "a1": PDRectangle(0.0, 0.0, 1684.0, 2384.0),
    "a2": PDRectangle(0.0, 0.0, 1191.0, 1684.0),
    "a3": PDRectangle(0.0, 0.0, 842.0, 1191.0),
    "a4": PDRectangle.A4,  # type: ignore[attr-defined]
    "a5": PDRectangle(0.0, 0.0, 420.0, 595.0),
    "a6": PDRectangle(0.0, 0.0, 298.0, 420.0),
}

_DEFAULT_PAGE_SIZE = "Letter"


# ---------------------------------------------------------------------------
# argparse wiring
# ---------------------------------------------------------------------------


def build_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    p = subparsers.add_parser(
        "imagetopdf",
        help="create a PDF document from images",
        description="Create a PDF document from one or more raster images. "
        "Each input image becomes a single page; the image is drawn at the "
        "lower-left corner of the page either at its intrinsic pixel size "
        "(default) or stretched to fill the page (-resize).",
    )
    p.add_argument(
        "-i", "--input", dest="inputs", required=True, nargs="+",
        metavar="IMAGE",
        help="one or more image files to convert (PNG, JPG/JPEG, TIFF, ...)",
    )
    p.add_argument(
        "-o", "--output", dest="output", required=True, metavar="OUTFILE",
        help="output PDF file",
    )
    p.add_argument(
        "-pageSize", "--pageSize", dest="page_size",
        default=_DEFAULT_PAGE_SIZE, metavar="SIZE",
        help="the page size to use: Letter, Legal, A0, A1, A2, A3, A4, A5, "
        "A6, or auto (= match each image's pixel dimensions). Default: Letter.",
    )
    p.add_argument(
        "-resize", "--resize", dest="resize", action="store_true",
        help="resize each image to fill the full page",
    )
    p.add_argument(
        "-orientation", "--orientation", dest="orientation",
        default="portrait", choices=("portrait", "landscape", "auto"),
        help="page orientation (default: portrait). 'auto' picks landscape "
        "when the image is wider than it is tall.",
    )
    # Legacy upstream flags retained for ImageToPDF compatibility — they
    # set the matching value on -orientation.
    p.add_argument(
        "-landscape", "--landscape", dest="_landscape",
        action="store_true",
        help="set orientation to landscape (alias for -orientation landscape)",
    )
    p.add_argument(
        "-autoOrientation", "--autoOrientation", dest="_auto_orientation",
        action="store_true",
        help="set orientation to auto (alias for -orientation auto)",
    )
    p.set_defaults(func=run)


# ---------------------------------------------------------------------------
# image embedding
# ---------------------------------------------------------------------------


def _create_jpeg_xobject(path: Path) -> PDImageXObject:
    """Embed a JPEG image verbatim using ``/DCTDecode``.

    Mirrors upstream ``JPEGFactory.createFromStream`` for the common
    ``ColorModel.RGB`` case (the only one Pillow's standard JPEG reader
    exposes without extra plugins).
    """
    raw = path.read_bytes()
    # Pillow gives us width/height/mode without decoding the pixels.
    with Image.open(path) as probe:
        probe.load()
        width, height = probe.size
        mode = probe.mode

    color_space = "DeviceGray" if mode == "L" else "DeviceRGB"
    if mode == "CMYK":
        color_space = "DeviceCMYK"

    cos = COSStream()
    cos.set_raw_data(raw)
    cos.set_item(COSName.FILTER, COSName.get_pdf_name("DCTDecode"))  # type: ignore[attr-defined]
    image = PDImageXObject(cos)
    image.set_width(width)
    image.set_height(height)
    image.set_bits_per_component(8)
    image.set_color_space(color_space)
    return image


def _create_lossless_xobject(path: Path) -> PDImageXObject:
    """Decode any Pillow-readable image to raw RGB pixels and embed it
    behind ``/FlateDecode``. Mirrors upstream ``LosslessFactory`` for the
    8-bit RGB case (the dominant input format)."""
    with Image.open(path) as src:
        src.load()
        if src.mode in ("RGBA", "LA", "P"):
            # Flatten transparency / palette to RGB; full /SMask handling
            # would require a second image XObject which the upstream
            # LosslessFactory only emits for true alpha — skipped here
            # since pypdfbox doesn't yet bind into the soft-mask helper.
            rgb = src.convert("RGB")
        elif src.mode == "L":
            rgb = src
        elif src.mode == "1":
            rgb = src.convert("L")
        elif src.mode == "CMYK":
            rgb = src
        else:
            rgb = src.convert("RGB")
        width, height = rgb.size
        pixel_bytes = rgb.tobytes()
        mode = rgb.mode

    if mode == "L":
        color_space = "DeviceGray"
    elif mode == "CMYK":
        color_space = "DeviceCMYK"
    else:
        color_space = "DeviceRGB"

    encoded = zlib.compress(pixel_bytes)
    cos = COSStream()
    cos.set_raw_data(encoded)
    cos.set_item(COSName.FILTER, COSName.FLATE_DECODE)  # type: ignore[attr-defined]
    image = PDImageXObject(cos)
    image.set_width(width)
    image.set_height(height)
    image.set_bits_per_component(8)
    image.set_color_space(color_space)
    return image


def create_image_xobject(path: Path) -> PDImageXObject:
    """Build a :class:`PDImageXObject` from ``path``. JPEGs are embedded
    verbatim as ``/DCTDecode``; everything else is decoded by Pillow and
    stored as ``/FlateDecode`` raw raster.

    Mirrors upstream ``PDImageXObject.createFromFileByExtension`` —
    extension-based dispatch with the same list of supported formats.
    """
    ext = path.suffix.lower().lstrip(".")
    if ext in ("jpg", "jpeg"):
        return _create_jpeg_xobject(path)
    return _create_lossless_xobject(path)


# ---------------------------------------------------------------------------
# page sizing
# ---------------------------------------------------------------------------


def _resolve_page_size(name: str) -> PDRectangle | None:
    """Resolve a page-size keyword to a :class:`PDRectangle`. Returns
    ``None`` for ``auto`` (caller derives the rectangle per-image).
    Unknown names fall back to Letter, matching upstream's
    ``createRectangle`` default."""
    key = (name or "").strip().lower()
    if key == "auto":
        return None
    return _PAGE_SIZES.get(key, PDRectangle.LETTER)  # type: ignore[attr-defined]


def _orient(media_box: PDRectangle, orientation: str, image: PDImageXObject) -> PDRectangle:
    """Apply orientation to ``media_box`` and return the actual rectangle.
    ``portrait`` keeps the box as-is; ``landscape`` swaps width/height;
    ``auto`` swaps when the image is wider than tall."""
    if orientation == "landscape":
        return PDRectangle(0.0, 0.0, media_box.get_height(), media_box.get_width())
    if orientation == "auto":
        if image.get_width() > image.get_height():
            return PDRectangle(0.0, 0.0, media_box.get_height(), media_box.get_width())
    return media_box


def _auto_media_box(image: PDImageXObject) -> PDRectangle:
    """Page rectangle that exactly matches the image's pixel dimensions
    (1 pixel == 1 pt). Used for ``-pageSize auto``."""
    return PDRectangle(0.0, 0.0, float(image.get_width()), float(image.get_height()))


# ---------------------------------------------------------------------------
# core
# ---------------------------------------------------------------------------


def images_to_pdf(
    inputs: Iterable[Path | str],
    output: Path | str,
    *,
    page_size: str = _DEFAULT_PAGE_SIZE,
    resize: bool = False,
    orientation: str = "portrait",
) -> None:
    """Build a multi-page PDF where each page carries one input image.

    Mirrors the body of upstream ``ImageToPDF#call`` plus the
    ``-autoOrientation`` / ``-landscape`` / ``-resize`` switches. The
    orientation argument here unifies upstream's two boolean flags into a
    single tri-state string (``portrait`` / ``landscape`` / ``auto``).
    """
    media_box_template = _resolve_page_size(page_size)
    doc = PDDocument()
    try:
        for image_path in inputs:
            path = Path(image_path)
            image = create_image_xobject(path)

            if media_box_template is None:
                # auto page size: match the image's pixel bounds.
                actual_media_box = _auto_media_box(image)
            else:
                actual_media_box = _orient(media_box_template, orientation, image)

            page = PDPage(actual_media_box)
            doc.add_page(page)
            with PDPageContentStream(doc, page) as contents:
                if resize:
                    contents.draw_image(
                        image,
                        0,
                        0,
                        actual_media_box.get_width(),
                        actual_media_box.get_height(),
                    )
                else:
                    contents.draw_image(
                        image,
                        0,
                        0,
                        float(image.get_width()),
                        float(image.get_height()),
                    )
        doc.save(output)
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def run(args: argparse.Namespace) -> int:
    inputs = [Path(p) for p in args.inputs]
    for p in inputs:
        if not p.is_file():
            print(f"imagetopdf: {p}: not a file", flush=True)
            return 4

    # Reconcile legacy upstream switches with the unified -orientation arg.
    orientation = (args.orientation or "portrait").lower()
    if getattr(args, "_landscape", False):
        orientation = "landscape"
    if getattr(args, "_auto_orientation", False):
        orientation = "auto"

    images_to_pdf(
        inputs,
        Path(args.output),
        page_size=args.page_size,
        resize=bool(args.resize),
        orientation=orientation,
    )
    return 0
