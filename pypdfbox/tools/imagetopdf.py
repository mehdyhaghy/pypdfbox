"""
``pypdfbox imagetopdf -i img1 [img2 ...] -o out.pdf [-pageSize SIZE]
[-resize] [-orientation ORI] [--margin-pt N]`` — build a PDF from one or
more raster images.

Mirrors upstream ``org.apache.pdfbox.tools.ImageToPDF``. Upstream loads
each image via ``PDImageXObject.createFromFileByExtension`` (delegating
to ``JPEGFactory`` / ``LosslessFactory``), creates one page per image,
and draws the image at ``(0, 0)`` either at its intrinsic pixel size or
stretched to the page when ``-resize`` is set.

pypdfbox builds the Image XObject inline in this CLI path rather than
routing through the separately ported ``JPEGFactory`` / ``LosslessFactory``
helpers:

* ``.jpg`` / ``.jpeg`` payloads embed verbatim as ``/DCTDecode``.
* every other Pillow-readable format (PNG, TIFF, BMP, GIF, ...) is
  decoded to RGB pixels and stored as a FlateDecode-compressed raster.

In addition to upstream's switches we expose a small superset for
practical CLI use:

* ``--page-size`` — extended catalog (LETTER, LEGAL, US-LEGAL, EXECUTIVE,
  TABLOID, LEDGER, A0..A6, B4, B5).
* ``--portrait`` / ``--landscape`` — explicit orientation flags
  (``--landscape`` mirrors upstream; ``--portrait`` is the implicit
  default and is exposed for symmetry).
* ``--auto-orientation`` — picks landscape automatically when the image
  is wider than tall (mirrors upstream ``-autoOrientation``).
* ``--margin-pt N`` — uniform white margin (in PDF points) on all four
  sides. With ``--resize`` the image is fit into the printable area
  (page minus margins) preserving aspect ratio; without ``--resize`` the
  image is positioned at the lower-left of the printable area at its
  intrinsic pixel size.

Exit codes follow upstream:
  0  success
  4  I/O error (raised as ``OSError`` and caught by ``cli.run_cli``)
"""
from __future__ import annotations

import argparse
import zlib
from collections.abc import Iterable
from pathlib import Path

from PIL import Image

from pypdfbox.cos import COSName, COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.graphics.image import PDImageXObject
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream

# ---------------------------------------------------------------------------
# page-size table (mirrors upstream ImageToPDF#createRectangle)
# ---------------------------------------------------------------------------

# Standard sizes in PDF user-space points (1pt = 1/72 inch). Values
# match Apache PDFBox's PDRectangle constants where they exist; the rest
# come from the ISO 216 / ANSI / North-American tables.
#
# Aliases (us-legal == legal, ledger == tabloid) are wired below so the
# CLI accepts both spellings; matches upstream's case-insensitive
# ``createRectangle`` lookup.
_LETTER = PDRectangle.from_width_height(PDRectangle.LETTER_WIDTH, PDRectangle.LETTER_HEIGHT)
_LEGAL = PDRectangle.from_width_height(PDRectangle.LEGAL_WIDTH, PDRectangle.LEGAL_HEIGHT)
_A4 = PDRectangle.from_width_height(PDRectangle.A4_WIDTH, PDRectangle.A4_HEIGHT)

_PAGE_SIZES: dict[str, PDRectangle] = {
    # North American
    "letter": _LETTER,
    "legal": _LEGAL,
    "us-legal": _LEGAL,
    "us_legal": _LEGAL,
    "uslegal": _LEGAL,
    "executive": PDRectangle(0.0, 0.0, 522.0, 756.0),
    "tabloid": PDRectangle(0.0, 0.0, 792.0, 1224.0),
    "ledger": PDRectangle(0.0, 0.0, 792.0, 1224.0),
    # ISO 216 A-series
    "a0": PDRectangle(0.0, 0.0, 2384.0, 3370.0),
    "a1": PDRectangle(0.0, 0.0, 1684.0, 2384.0),
    "a2": PDRectangle(0.0, 0.0, 1191.0, 1684.0),
    "a3": PDRectangle(0.0, 0.0, 842.0, 1191.0),
    "a4": _A4,
    "a5": PDRectangle(0.0, 0.0, 420.0, 595.0),
    "a6": PDRectangle(0.0, 0.0, 298.0, 420.0),
    # ISO 216 B-series (commonly requested; subset only)
    "b4": PDRectangle(0.0, 0.0, 709.0, 1001.0),
    "b5": PDRectangle(0.0, 0.0, 499.0, 709.0),
}

_DEFAULT_PAGE_SIZE = "Letter"
_FILTER = COSName.get_pdf_name("Filter")
_FLATE_DECODE = COSName.get_pdf_name("FlateDecode")


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
        "-pageSize", "--pageSize", "--page-size", dest="page_size",
        default=_DEFAULT_PAGE_SIZE, metavar="SIZE",
        help="page size: Letter, Legal, US-Legal, Executive, Tabloid, Ledger, "
        "A0..A6, B4, B5, or 'auto' (= match each image's pixel dimensions). "
        "Default: Letter.",
    )
    p.add_argument(
        "-resize", "--resize", dest="resize", action="store_true",
        help="resize each image to fit the printable area (page minus "
        "margins). Aspect ratio is preserved when --margin-pt > 0; with "
        "no margin the image is stretched to fill the page (upstream "
        "behavior).",
    )
    p.add_argument(
        "-orientation", "--orientation", dest="orientation",
        default="portrait", type=_parse_orientation,
        choices=("portrait", "landscape", "auto"),
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
        "--portrait", dest="_portrait", action="store_true",
        help="set orientation to portrait (alias for -orientation portrait); "
        "default — exposed for symmetry with --landscape.",
    )
    p.add_argument(
        "-autoOrientation", "--autoOrientation", "--auto-orientation",
        dest="_auto_orientation", action="store_true",
        help="rotate page to landscape when the image is wider than tall "
        "(alias for -orientation auto).",
    )
    p.add_argument(
        "--margin-pt", dest="margin_pt", type=float, default=0.0,
        metavar="N",
        help="uniform white margin in PDF points (1pt = 1/72 in) on all "
        "four sides. Default: 0.",
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
    cos.set_item(_FILTER, COSName.get_pdf_name("DCTDecode"))
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
            # LosslessFactory only emits for true alpha. The CLI's inline
            # path intentionally stays on a single image XObject here.
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
    cos.set_item(_FILTER, _FLATE_DECODE)
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
    ``createRectangle`` default.

    Hyphens, underscores and case are normalised so callers can pass
    ``"US-Legal"``, ``"us_legal"`` or ``"USLEGAL"`` interchangeably.
    """
    key = (name or "").strip().lower()
    if key == "auto":
        return None
    # Try the literal lookup first, then the hyphen/underscore-normalized
    # form (so 'usletter' -> 'usletter' miss falls back to 'us-letter' if
    # later added; harmless today).
    rect = _PAGE_SIZES.get(key)
    if rect is None:
        rect = _PAGE_SIZES.get(key.replace("_", "-"))
    if rect is None:
        rect = _PAGE_SIZES.get(key.replace("-", "_"))
    if rect is None:
        rect = _PAGE_SIZES.get(key.replace("-", "").replace("_", ""))
    return rect if rect is not None else _LETTER


def _normalize_orientation(value: str) -> str:
    """Return a canonical orientation value or raise ``ValueError``."""
    orientation = (value or "portrait").strip().lower()
    if orientation not in {"portrait", "landscape", "auto"}:
        raise ValueError(
            "orientation must be one of: portrait, landscape, auto"
        )
    return orientation


def _parse_orientation(value: str) -> str:
    """argparse adapter for case-insensitive orientation values."""
    try:
        return _normalize_orientation(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def _orient(media_box: PDRectangle, orientation: str, image: PDImageXObject) -> PDRectangle:
    """Apply orientation to ``media_box`` and return the actual rectangle.
    ``portrait`` keeps the box as-is; ``landscape`` swaps width/height;
    ``auto`` swaps when the image is wider than tall."""
    if orientation == "landscape":
        return PDRectangle(0.0, 0.0, media_box.get_height(), media_box.get_width())
    if orientation == "auto" and image.get_width() > image.get_height():
        return PDRectangle(0.0, 0.0, media_box.get_height(), media_box.get_width())
    return media_box


def _auto_media_box(image: PDImageXObject) -> PDRectangle:
    """Page rectangle that exactly matches the image's pixel dimensions
    (1 pixel == 1 pt). Used for ``-pageSize auto``."""
    return PDRectangle(0.0, 0.0, float(image.get_width()), float(image.get_height()))


# ---------------------------------------------------------------------------
# core
# ---------------------------------------------------------------------------


def _fit_into(image: PDImageXObject, max_w: float, max_h: float) -> tuple[float, float]:
    """Scale ``image``'s pixel size into a box of ``max_w`` x ``max_h``
    preserving aspect ratio. Returns the (width, height) in PDF points.
    If the image already fits in either dimension we still scale so it
    consumes the printable area — matching the user expectation of
    ``--resize``."""
    iw = float(image.get_width())
    ih = float(image.get_height())
    if iw <= 0 or ih <= 0:  # pragma: no cover — defensive
        return max_w, max_h
    scale = min(max_w / iw, max_h / ih)
    return iw * scale, ih * scale


def images_to_pdf(
    inputs: Iterable[Path | str],
    output: Path | str,
    *,
    page_size: str = _DEFAULT_PAGE_SIZE,
    resize: bool = False,
    orientation: str = "portrait",
    margin_pt: float = 0.0,
) -> None:
    """Build a multi-page PDF where each page carries one input image.

    Mirrors the body of upstream ``ImageToPDF#call`` plus the
    ``-autoOrientation`` / ``-landscape`` / ``-resize`` switches. The
    orientation argument here unifies upstream's two boolean flags into a
    single tri-state string (``portrait`` / ``landscape`` / ``auto``).

    ``margin_pt`` adds a uniform white margin (in PDF points) on all
    four sides of every page; with ``resize=True`` the image is fit into
    the printable area preserving aspect ratio, otherwise it is placed
    at the lower-left of the printable area at its intrinsic pixel size.
    """
    media_box_template = _resolve_page_size(page_size)
    orientation = _normalize_orientation(orientation)
    margin = max(0.0, float(margin_pt))
    doc = PDDocument()
    try:
        for image_path in inputs:
            path = Path(image_path)
            image = create_image_xobject(path)

            if media_box_template is None:
                # auto page size: match the image's pixel bounds (plus
                # margin on all sides if requested).
                inner = _auto_media_box(image)
                actual_media_box = PDRectangle(
                    0.0, 0.0,
                    inner.get_width() + 2 * margin,
                    inner.get_height() + 2 * margin,
                )
            else:
                actual_media_box = _orient(media_box_template, orientation, image)

            page = PDPage(actual_media_box)
            doc.add_page(page)

            page_w = actual_media_box.get_width()
            page_h = actual_media_box.get_height()
            printable_w = max(0.0, page_w - 2 * margin)
            printable_h = max(0.0, page_h - 2 * margin)

            with PDPageContentStream(doc, page) as contents:
                if resize:
                    if margin > 0.0:
                        # Fit into the printable area preserving aspect.
                        draw_w, draw_h = _fit_into(image, printable_w, printable_h)
                        # Center within the printable area.
                        x = margin + (printable_w - draw_w) / 2.0
                        y = margin + (printable_h - draw_h) / 2.0
                        contents.draw_image(image, x, y, draw_w, draw_h)
                    else:
                        # Upstream behavior: stretch to full media box.
                        contents.draw_image(image, 0, 0, page_w, page_h)
                else:
                    contents.draw_image(
                        image,
                        margin,
                        margin,
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
    # Boolean flags don't preserve CLI ordering through argparse, so we
    # pick a deterministic precedence: among the aliases, auto wins,
    # then landscape, then portrait. Aliases override -orientation.
    # This matches upstream where -autoOrientation overrides -landscape.
    orientation = args.orientation or "portrait"
    if getattr(args, "_portrait", False):
        orientation = "portrait"
    if getattr(args, "_landscape", False):
        orientation = "landscape"
    if getattr(args, "_auto_orientation", False):
        orientation = "auto"

    margin_pt = float(getattr(args, "margin_pt", 0.0) or 0.0)
    if margin_pt < 0:
        print(f"imagetopdf: --margin-pt must be >= 0 (got {margin_pt})", flush=True)
        return 4

    images_to_pdf(
        inputs,
        Path(args.output),
        page_size=args.page_size,
        resize=bool(args.resize),
        orientation=orientation,
        margin_pt=margin_pt,
    )
    return 0
