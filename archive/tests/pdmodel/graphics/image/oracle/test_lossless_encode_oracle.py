"""Live PDFBox differential parity for ``LosslessFactory.create_from_image``
across the colour-space cases NOT covered by ``test_image_encode_oracle.py``
(which exercises only RGB / RGBA): **8-bit grayscale**, **grayscale + alpha**,
and **indexed/palette** rasters.

Each source raster is authored deterministically with Pillow and written as a
PNG so the Java probe (``oracle/probes/LosslessEncodeProbe.java`` ``make``) can
``ImageIO.read`` the identical bytes and build the upstream XObject via
``LosslessFactory.createFromImage``. pypdfbox builds the equivalent XObject from
the same PIL source. We then compare, per image XObject:

* **dict fields** read directly off the created XObject — ``/Filter`` name,
  dims, BPC, and ``/SMask`` presence — which must match PDFBox.
* **colour-space token** — pinned per case. Two are *intentional, documented*
  divergences (PRD "behaviour over style": the decoded raster is what matters,
  and both tokens describe the identical pixels):

    - **indexed**: upstream ``createFromImage`` has *no* indexed path (its
      bytecode routes only gray-fast-path / PredictorEncoder / RGB-fallback —
      it never emits ``/Indexed``), so an ``IndexColorModel`` PNG comes out as
      ``/DeviceRGB``. pypdfbox keys on PIL ``"P"`` mode and emits the spec-equal
      ``/Indexed [/DeviceRGB hival <lookup>]`` (a tested port choice). When read
      back through the *same* Java renderer the decoded raster is **bit-identical**
      (MAD 0.00 — pinned below), so the two encodings are visually equivalent.
    - **gray + alpha**: upstream routes ``LA`` through ``PredictorEncoder``,
      which wraps the body in an sRGB-gray ``/ICCBased`` colour space; pypdfbox
      emits the equivalent ``/DeviceGray``. Both carry the alpha as an 8-bit
      ``/DeviceGray`` ``/SMask``.

* **encode→decode round-trip** (pypdfbox only): ``create_from_image`` then
  ``get_image()`` must reproduce the *source* raster bit-for-bit. This is the
  load-bearing lossless guarantee and is library-internal (no gamma boundary),
  so it is asserted at MAXDIFF 0.

Why the decoded grid is NOT cross-compared for gray / LA: Pillow's ``"L"`` mode
preserves the PNG's stored (sRGB-encoded) sample bytes verbatim, whereas Java's
``ImageIO.read`` produces a ``TYPE_BYTE_GRAY`` BufferedImage whose ColorSpace is
*linear* gray — it gamma-decodes the same PNG bytes on read. Each factory is
faithful to its own library's interpretation of the identical PNG, so their
stored DeviceGray samples (and thus the decoded grids) legitimately differ by
the sRGB transfer curve. That divergence lives at the Pillow-vs-Java2D source
boundary, not in pypdfbox's encoder — proven here by the exact pypdfbox
round-trip. The indexed case has no such boundary (palette entries are stored
as raw RGB triplets, not gamma-mapped), so its decoded grid IS cross-compared
and lands at MAD 0.00.
"""

from __future__ import annotations

from PIL import Image

from pypdfbox.cos import COSArray, COSName, COSStream
from pypdfbox.pdmodel.graphics.image.lossless_factory import LosslessFactory
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from pypdfbox.pdmodel.pd_resources import PDResources
from tests.oracle.harness import requires_oracle, run_probe, run_probe_text

_GRID = 16
_FILTER = COSName.get_pdf_name("Filter")
_SIZE = 48


# ---------------------------------------------------------------------------
# deterministic source rasters (written as PNG for the Java probe)
# ---------------------------------------------------------------------------


def _make_gray() -> Image.Image:
    """8-bit grayscale diagonal ramp: value = (x + y) * 255 / (2*(size-1))."""
    img = Image.new("L", (_SIZE, _SIZE))
    px = img.load()
    for y in range(_SIZE):
        for x in range(_SIZE):
            px[x, y] = (x + y) * 255 // (2 * (_SIZE - 1))
    return img


def _make_gray_alpha() -> Image.Image:
    """Grayscale diagonal ramp with an inverted-value alpha channel (so the
    alpha gradient is independent of the body)."""
    gray = _make_gray()
    alpha = Image.eval(gray, lambda v: 255 - v)
    return Image.merge("LA", (gray, alpha))


def _make_indexed() -> Image.Image:
    """A 16-colour adaptive-palette image of an RGB colour wedge — exercises
    the ``/Indexed [/DeviceRGB hival <lookup>]`` path."""
    rgb = Image.new("RGB", (_SIZE, _SIZE))
    px = rgb.load()
    for y in range(_SIZE):
        for x in range(_SIZE):
            px[x, y] = (x * 255 // (_SIZE - 1), y * 255 // (_SIZE - 1), 96)
    return rgb.convert("P", palette=Image.ADAPTIVE, colors=16)


# ---------------------------------------------------------------------------
# pypdfbox PDF construction (mirrors LosslessEncodeProbe.make: one image / page)
# ---------------------------------------------------------------------------


def _build_py_pdf(source: Image.Image, out_path) -> tuple[PDDocument, object]:
    """Build a one-page PDF via pypdfbox; return (document, created XObject).

    The caller must ``close()`` the document *after* inspecting the XObject —
    closing it releases the scratch-file buffer backing the image stream, so
    ``get_image()`` / dict reads must happen while it is still open.
    """
    document = PDDocument()
    image = LosslessFactory.create_from_image(document, source)
    page = PDPage(PDRectangle(0.0, 0.0, 200.0, 200.0))
    document.add_page(page)
    page.set_resources(PDResources())
    cs = PDPageContentStream(document, page)
    try:
        cs.draw_image(image, 10.0, 10.0, 180.0, 180.0)
    finally:
        cs.close()
    with open(out_path, "wb") as fh:
        document.save(fh)
    return document, image


# ---------------------------------------------------------------------------
# probe output parsing
# ---------------------------------------------------------------------------


def _filter_name(cos: COSStream) -> str:
    value = cos.get_dictionary_object(_FILTER)
    if isinstance(value, COSName):
        return value.get_name()
    if isinstance(value, COSArray) and len(value) == 1:
        item = value.get(0)
        if isinstance(item, COSName):
            return item.get_name()
    return "none"


def _read_probe_row(pdf_path) -> dict:
    """Parse the single image-XObject line emitted by ``read`` for a PDF."""
    out = run_probe_text("LosslessEncodeProbe", "read", str(pdf_path))
    line = next(ln for ln in out.splitlines() if ln.startswith("image "))
    toks = line.split()
    grid_at = toks.index("grid")
    return {
        "filter": toks[toks.index("filter") + 1],
        "cs": toks[toks.index("cs") + 1],
        "w": int(toks[toks.index("w") + 1]),
        "h": int(toks[toks.index("h") + 1]),
        "bpc": int(toks[toks.index("bpc") + 1]),
        "smask": int(toks[toks.index("smask") + 1]),
        "grid": [int(t) for t in toks[grid_at + 1 :]],
    }


def _read_py_grid(pdf_path) -> list[int]:
    """Render pypdfbox's PDF through the SAME Java probe (so the decoder is
    identical to the upstream side — a pure encode differential)."""
    return _read_probe_row(pdf_path)["grid"]


def _build_java_pdf(png_path, out_path) -> None:
    # Use run_probe directly (compiles on demand); the `make` subcommand has
    # no stdout we need.
    run_probe("LosslessEncodeProbe", "make", str(png_path), str(out_path))


def _grid_mad_maxdiff(a: list[int], b: list[int]) -> tuple[float, int]:
    assert len(a) == len(b) == _GRID * _GRID
    diffs = [abs(x - y) for x, y in zip(a, b, strict=True)]
    return sum(diffs) / len(diffs), max(diffs)


# ---------------------------------------------------------------------------
# tests
# ---------------------------------------------------------------------------


@requires_oracle
def test_gray_encode_matches_pdfbox(tmp_path) -> None:
    """8-bit grayscale source -> LosslessFactory: /FlateDecode /DeviceGray
    8 BPC, no /SMask, dims match PDFBox; pypdfbox round-trips losslessly."""
    source = _make_gray()
    png = tmp_path / "gray.png"
    source.save(png, format="PNG")

    document, py_image = _build_py_pdf(source, tmp_path / "py.pdf")
    try:
        _build_java_pdf(png, tmp_path / "java.pdf")
        java = _read_probe_row(tmp_path / "java.pdf")

        cos = py_image.get_cos_object()
        assert _filter_name(cos) == java["filter"] == "FlateDecode"
        assert py_image.get_color_space().get_name() == java["cs"] == "DeviceGray"
        assert (py_image.get_width(), py_image.get_height()) == (
            java["w"],
            java["h"],
        ) == (_SIZE, _SIZE)
        assert py_image.get_bits_per_component() == java["bpc"] == 8
        assert (
            1 if py_image.get_soft_mask() is not None else 0
        ) == java["smask"] == 0

        # Lossless round-trip: encode then decode reproduces source exactly.
        decoded = py_image.get_image().convert("L")
        assert decoded.tobytes() == source.tobytes()
    finally:
        document.close()


@requires_oracle
def test_gray_alpha_encode_matches_pdfbox(tmp_path) -> None:
    """LA source -> /FlateDecode gray body + 8-bit /DeviceGray /SMask. Upstream
    wraps the body in /ICCBased; pypdfbox emits the equivalent /DeviceGray (a
    documented behaviour-over-style divergence). Both carry the /SMask and
    round-trip losslessly in pypdfbox."""
    source = _make_gray_alpha()
    png = tmp_path / "la.png"
    source.save(png, format="PNG")

    document, py_image = _build_py_pdf(source, tmp_path / "py.pdf")
    try:
        _build_java_pdf(png, tmp_path / "java.pdf")
        java = _read_probe_row(tmp_path / "java.pdf")

        cos = py_image.get_cos_object()
        assert _filter_name(cos) == java["filter"] == "FlateDecode"
        assert (py_image.get_width(), py_image.get_height()) == (
            java["w"],
            java["h"],
        ) == (_SIZE, _SIZE)
        assert py_image.get_bits_per_component() == java["bpc"] == 8
        # The headline: alpha was split into a /SMask on both sides.
        assert (
            1 if py_image.get_soft_mask() is not None else 0
        ) == java["smask"] == 1
        # Documented colour-space divergence (both describe an 8-bit gray body).
        assert py_image.get_color_space().get_name() == "DeviceGray"
        assert java["cs"] == "ICCBased"

        # The SMask itself: 8-bit /DeviceGray of matching dims.
        smask = py_image.get_soft_mask()
        assert smask is not None
        assert smask.get_color_space().get_name() == "DeviceGray"
        assert (smask.get_width(), smask.get_height()) == (_SIZE, _SIZE)
        assert smask.get_bits_per_component() == 8

        # Lossless round-trip on both body and alpha.
        decoded = py_image.get_image().convert("LA")
        assert decoded.tobytes() == source.tobytes()
    finally:
        document.close()


@requires_oracle
def test_indexed_encode_matches_pdfbox(tmp_path) -> None:
    """Indexed/palette source -> pypdfbox /Indexed [/DeviceRGB ...] vs upstream
    /DeviceRGB (upstream has no indexed path). Decoded raster is bit-identical
    when read back through the SAME renderer (MAD 0.00), proving the two
    encodings are visually equivalent. pypdfbox round-trips losslessly."""
    source = _make_indexed()
    png = tmp_path / "idx.png"
    source.save(png, format="PNG")

    document, py_image = _build_py_pdf(source, tmp_path / "py.pdf")
    try:
        _build_java_pdf(png, tmp_path / "java.pdf")
        java = _read_probe_row(tmp_path / "java.pdf")

        cos = py_image.get_cos_object()
        assert _filter_name(cos) == java["filter"] == "FlateDecode"
        assert (py_image.get_width(), py_image.get_height()) == (
            java["w"],
            java["h"],
        ) == (_SIZE, _SIZE)
        assert py_image.get_bits_per_component() == java["bpc"] == 8
        assert (
            1 if py_image.get_soft_mask() is not None else 0
        ) == java["smask"] == 0
        # Documented colour-space divergence: pypdfbox keeps the palette as
        # /Indexed; upstream de-indexes to /DeviceRGB.
        assert py_image.get_color_space().get_name() == "Indexed"
        assert java["cs"] == "DeviceRGB"
        # The /Indexed lookup is built over /DeviceRGB (PRD: mirror upstream's
        # array shape [/Indexed base hival lookup]).
        cs_cos = cos.get_dictionary_object(COSName.get_pdf_name("ColorSpace"))
        assert isinstance(cs_cos, COSArray)
        assert cs_cos.get(0) == COSName.get_pdf_name("Indexed")
        assert cs_cos.get(1) == COSName.get_pdf_name("DeviceRGB")

        # Decoded-raster parity through the identical renderer: bit-exact (the
        # palette is stored as raw RGB triplets, so there is no gamma boundary).
        py_grid = _read_py_grid(tmp_path / "py.pdf")
        mad, maxdiff = _grid_mad_maxdiff(java["grid"], py_grid)
        assert mad == 0.0 and maxdiff == 0, (
            f"indexed decoded raster diverges from upstream de-index: "
            f"mad={mad} maxdiff={maxdiff}"
        )

        # Lossless round-trip in pypdfbox: encode->decode reproduces source RGB.
        decoded = py_image.get_image().convert("RGB")
        assert decoded.tobytes() == source.convert("RGB").tobytes()
    finally:
        document.close()
