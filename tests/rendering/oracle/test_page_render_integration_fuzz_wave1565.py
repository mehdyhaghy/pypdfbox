"""Live PDFBox differential FUZZ of END-TO-END combined-page rendering — the
integration of ``PDFRenderer.renderImageWithDPI`` over a whole page that mixes
text + a filled path + a line + (sometimes) an inline image + a clip, across
DPI 72/150/300 and page ``/Rotate`` 0/90/180/270 (PDF 32000-1 §7.7.3.3 page
geometry, §8.5 path painting, §8.9 images, §9 text; Apache PDFBox
``PDFRenderer`` / ``PageDrawer``).

Prior waves fuzzed the individual paint paths in isolation on an otherwise
blank page — text (1558), path (1547), image (1559), shading (1560), tiling
(1563). This wave is the INTEGRATION render: one page assembled from a single
content stream combining several operator families, so the test pins that the
renderer composes a *whole page* correctly (dimensions scale with DPI, content
lands on the right side under rotation, a clip actually limits paint, an empty
page stays white, a non-zero MediaBox origin is honoured).

Pixel-exact parity is impossible (Java2D vs Pillow/skia AA — see
``test_render_oracle.py`` / CHANGES.md), so ``PageRenderIntegrationFuzzProbe``
projects only COARSE whole-page facts:

* exact rendered pixel dimensions (a mismatch is a real DPI/rotation bug);
* the non-white pixel count, bucketed into {empty, sparse, moderate, dense}
  (exact counts drift with AA; a region one side paints must not be blank on
  the other);
* the painted bounding box within a generous ``_BBOX_SLOP`` px tolerance;
* the *dominant painted quadrant* — a rotation that places content on the
  wrong side is caught even when the global bbox/bucket survive.

Fixtures are tiny one-page PDFs synthesised in-memory from a raw content stream
(no committed binaries), matching ``test_page_drawer_path_fuzz_wave1547.py``.
The image case uses an inline image (``BI``/``ID``/``EI``) so no external
binary or factory round-trip is involved.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from pypdfbox.cos import COSDictionary, COSName, COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font
from pypdfbox.pdmodel.pd_resources import PDResources
from pypdfbox.rendering import PDFRenderer
from tests.oracle.harness import requires_oracle, run_probe_text

_WHITE_THRESHOLD = 250  # luma < this counts as painted (matches the probe)
_BBOX_SLOP = 4  # px tolerance on the painted bbox edges (AA fringe)


# ---------------------------------------------------------------------------
# A reusable combined-content stream: a filled grey rectangle (lower-left),
# a black diagonal line, and a line of Helvetica text near the top. 1 user
# unit == 1 px at 72 DPI. Deliberately asymmetric so rotation is observable.
# ---------------------------------------------------------------------------
def _combined_stream(page_w: float, page_h: float, origin_x: float = 0.0,
                     origin_y: float = 0.0) -> bytes:
    ox = origin_x
    oy = origin_y
    return (
        # filled rect anchored bottom-left of the visible box
        f"0.5 0.5 0.5 rg\n{ox + 20:.1f} {oy + 20:.1f} 60 40 re f\n"
        # diagonal stroked line across the lower half
        f"0 0 0 RG 2 w\n{ox + 20:.1f} {oy + 20:.1f} m "
        f"{ox + page_w - 20:.1f} {oy + page_h / 2:.1f} l S\n"
        # text near the top-left
        "BT /F1 18 Tf 0 0 0 rg "
        f"{ox + 20:.1f} {oy + page_h - 30:.1f} Td (Mix) Tj ET\n"
    ).encode("ascii")


# An inline image (8x8 RGB checkerboard) scaled into a box on the page,
# combined with a filled rect + text. Inline image avoids any external binary.
def _image_stream(page_w: float, page_h: float) -> bytes:
    # 8x8 RGB: alternate black / white pixels => grey-ish when downsampled.
    px = bytearray()
    for row in range(8):
        for col in range(8):
            v = 0 if (row + col) % 2 == 0 else 255
            px += bytes((v, v, v))
    # Inline image dictionary + raw RGB samples. Place it in the upper area.
    header = (
        f"0.5 0.5 0.5 rg\n20 20 60 40 re f\n"
        f"BT /F1 14 Tf 0 0 0 rg 20 {page_h - 24:.1f} Td (Img) Tj ET\n"
        f"q {page_w - 80:.1f} 0 0 {page_h / 3:.1f} {page_w / 2:.1f} "
        f"{page_h / 2:.1f} cm\n"
        "BI /W 8 /H 8 /CS /RGB /BPC 8 ID\n"
    ).encode("ascii")
    return header + bytes(px) + b"\nEI Q\n"


# A page whose only content is a clip rectangle limiting a full-page fill, so
# paint appears ONLY in the clipped sub-region.
def _clip_stream(page_w: float, page_h: float) -> bytes:
    return (
        # clip to a 40x40 box near the bottom-left, then fill the whole page
        f"30 30 40 40 re W n\n0 0 0 rg 0 0 {page_w:.1f} {page_h:.1f} re f\n"
    ).encode("ascii")


# ---------------------------------------------------------------------------
# Cases: (label, content-stream bytes, page rect, rotation, dpi).
# Page rects are 200x300 (non-square) so the 90/270 width/height swap is
# observable. mediabox_origin uses a non-zero lower-left corner.
# ---------------------------------------------------------------------------
def _cases() -> dict[str, tuple[bytes, PDRectangle, int, float]]:
    w, h = 200.0, 300.0
    combined = _combined_stream(w, h)
    cases: dict[str, tuple[bytes, PDRectangle, int, float]] = {
        # combined text + rect + line at the three standard DPI
        "combined_dpi72": (combined, PDRectangle(0, 0, w, h), 0, 72.0),
        "combined_dpi150": (combined, PDRectangle(0, 0, w, h), 0, 150.0),
        "combined_dpi300": (combined, PDRectangle(0, 0, w, h), 0, 300.0),
        # rotation sweep at 72 DPI — output orientation + content placement
        "combined_rot0": (combined, PDRectangle(0, 0, w, h), 0, 72.0),
        "combined_rot90": (combined, PDRectangle(0, 0, w, h), 90, 72.0),
        "combined_rot180": (combined, PDRectangle(0, 0, w, h), 180, 72.0),
        "combined_rot270": (combined, PDRectangle(0, 0, w, h), 270, 72.0),
        # rotation also at a higher DPI (compose + scale interaction)
        "combined_rot90_dpi150": (combined, PDRectangle(0, 0, w, h), 90, 150.0),
        # page combining an inline image with rect + text
        "image_combined_dpi72": (
            _image_stream(w, h), PDRectangle(0, 0, w, h), 0, 72.0,
        ),
        "image_combined_dpi150": (
            _image_stream(w, h), PDRectangle(0, 0, w, h), 0, 150.0,
        ),
        # clip limiting paint to a sub-region
        "clip_subregion_dpi72": (
            _clip_stream(w, h), PDRectangle(0, 0, w, h), 0, 72.0,
        ),
        "clip_subregion_dpi150": (
            _clip_stream(w, h), PDRectangle(0, 0, w, h), 0, 150.0,
        ),
        # empty page — all white
        "empty_dpi72": (b"\n", PDRectangle(0, 0, w, h), 0, 72.0),
        "empty_dpi150": (b"\n", PDRectangle(0, 0, w, h), 0, 150.0),
        # non-zero MediaBox origin — content drawn relative to the origin
        "mediabox_origin_dpi72": (
            _combined_stream(w, h, 50.0, 80.0),
            PDRectangle(50.0, 80.0, 50.0 + w, 80.0 + h),
            0,
            72.0,
        ),
        # square page so 90 swap is a no-op on dims but content still rotates
        "square_rot90": (
            _combined_stream(200.0, 200.0),
            PDRectangle(0, 0, 200.0, 200.0),
            90,
            72.0,
        ),
    }
    return cases


_CASES = _cases()


# ---------------------------------------------------------------------------
# Expected emptiness, derived from PDFBox 3.0.7 semantics. Used by the
# oracle-free pin so the corrected behaviour stays green without the live jar.
# ---------------------------------------------------------------------------
_EXPECT_PAINTED: dict[str, bool] = {label: (label not in {"empty_dpi72", "empty_dpi150"})
                                    for label in _CASES}


# ---------------------------------------------------------------------------
# fixture builder + fingerprint helpers
# ---------------------------------------------------------------------------
def _build(label: str, out: Path) -> Path:
    content, rect, rotation, _dpi = _CASES[label]
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(rect)
    res = PDResources()
    # Register Helvetica as /F1 so the text operators resolve (a
    # Standard-14 font dict, as the upstream paired tests build).
    font_dict = COSDictionary()
    font_dict.set_item(COSName.TYPE, COSName.get_pdf_name("Font"))
    font_dict.set_item(
        COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Type1")
    )
    font_dict.set_item(
        COSName.get_pdf_name("BaseFont"), COSName.get_pdf_name("Helvetica")
    )
    res.put(COSName.get_pdf_name("F1"), PDType1Font(font_dict))
    page.set_resources(res)
    if rotation:
        page.set_rotation(rotation)
    doc.add_page(page)
    stream = COSStream()
    stream.set_raw_data(content)
    page.get_cos_object().set_item(COSName.CONTENTS, stream)
    doc.save(str(out))
    doc.close()
    return out


def _painted_facts(
    img: Image.Image,
) -> tuple[int, tuple[int, int, int, int], tuple[int, int, int, int]]:
    """(painted, bbox, (tl, tr, bl, br)) — mirrors the probe exactly."""
    gray = img.convert("L")
    width, height = gray.size
    pixels = gray.load()
    halfx = width // 2
    halfy = height // 2
    painted = 0
    minx = miny = maxx = maxy = -1
    tl = tr = bl = br = 0
    for y in range(height):
        for x in range(width):
            if pixels[x, y] < _WHITE_THRESHOLD:
                painted += 1
                if minx < 0 or x < minx:
                    minx = x
                if miny < 0 or y < miny:
                    miny = y
                if x > maxx:
                    maxx = x
                if y > maxy:
                    maxy = y
                left = x < halfx
                top = y < halfy
                if top and left:
                    tl += 1
                elif top:
                    tr += 1
                elif left:
                    bl += 1
                else:
                    br += 1
    return painted, (minx, miny, maxx, maxy), (tl, tr, bl, br)


def _oracle_facts(
    fixture: Path, dpi: float
) -> tuple[
    tuple[int, int], int, tuple[int, int, int, int], tuple[int, int, int, int]
]:
    lines = run_probe_text(
        "PageRenderIntegrationFuzzProbe", str(fixture), "0", repr(dpi)
    ).splitlines()
    width, height = (int(v) for v in lines[0].split())
    vals = [int(v) for v in lines[1].split()]
    painted = vals[0]
    bbox = (vals[1], vals[2], vals[3], vals[4])
    quad = tuple(int(v) for v in lines[2].split())
    return (width, height), painted, bbox, quad  # type: ignore[return-value]


def _bucket(painted: int, total_px: int) -> str:
    if painted == 0:
        return "empty"
    frac = painted / total_px
    if frac < 0.01:
        return "sparse"
    if frac < 0.20:
        return "moderate"
    return "dense"


def _dominant_quadrant(quad: tuple[int, int, int, int]) -> str | None:
    """The quadrant holding > 45% of paint, else None (paint is spread)."""
    total = sum(quad)
    if total == 0:
        return None
    names = ("tl", "tr", "bl", "br")
    idx = max(range(4), key=lambda i: quad[i])
    if quad[idx] / total > 0.45:
        return names[idx]
    return None


# ---------------------------------------------------------------------------
# differential tests
# ---------------------------------------------------------------------------
@requires_oracle
@pytest.mark.parametrize("label", list(_CASES), ids=list(_CASES))
def test_page_render_integration_fuzz_matches_pdfbox(
    label: str, tmp_path: Path
) -> None:
    """Each combined-page case must match Apache PDFBox's *gross whole-page
    facts*: identical dimensions (DPI/rotation arithmetic), the same emptiness
    verdict + painted bucket, a painted bbox within ``_BBOX_SLOP`` px, and —
    when paint concentrates in one quadrant — the SAME dominant quadrant (a
    rotation landing content on the wrong side is caught here). Exact pixel
    counts and sub-pixel AA are expected to diverge and are NOT compared."""
    _content, _rect, _rotation, dpi = _CASES[label]
    fixture = _build(label, tmp_path / f"{label}.pdf")

    (java_w, java_h), java_painted, java_bbox, java_quad = _oracle_facts(
        fixture, dpi
    )

    with PDDocument.load(fixture) as doc:
        img = PDFRenderer(doc).render_image_with_dpi(0, dpi)
    py_w, py_h = img.size
    py_painted, py_bbox, py_quad = _painted_facts(img)

    # (a) Exact pixel dimensions — a mismatch is a real DPI/rotation bug.
    assert (py_w, py_h) == (java_w, java_h), (
        f"{label}: rendered dims diverge: py={py_w}x{py_h} "
        f"java={java_w}x{java_h}"
    )

    total_px = java_w * java_h
    java_empty = java_painted == 0
    py_empty = py_painted == 0

    # (b) Emptiness verdict must agree — the real-bug signal.
    assert py_empty == java_empty, (
        f"{label}: painted-emptiness diverges — pypdfbox painted "
        f"{py_painted}px, java painted {java_painted}px."
    )

    if java_empty:
        return

    # (c) Coarse pixel-count bucket must agree (drift-tolerant).
    java_bucket = _bucket(java_painted, total_px)
    py_bucket = _bucket(py_painted, total_px)
    assert py_bucket == java_bucket, (
        f"{label}: painted bucket diverges py={py_bucket}({py_painted}) "
        f"java={java_bucket}({java_painted}) — more than AA drift"
    )

    # (d) Painted bbox within slop (AA fringes the box by a few px).
    for axis, (p, j) in enumerate(zip(py_bbox, java_bbox, strict=True)):
        assert abs(p - j) <= _BBOX_SLOP, (
            f"{label}: painted bbox axis {axis} diverges py={py_bbox} "
            f"java={java_bbox} (slop={_BBOX_SLOP})"
        )

    # (e) Dominant painted quadrant — catches rotation placing content on the
    #     wrong side. Only assert when BOTH sides actually have a dominant
    #     quadrant (spread paint has no meaningful winner).
    java_dom = _dominant_quadrant(java_quad)
    py_dom = _dominant_quadrant(py_quad)
    if java_dom is not None and py_dom is not None:
        assert py_dom == java_dom, (
            f"{label}: dominant painted quadrant diverges py={py_dom}"
            f"{py_quad} java={java_dom}{java_quad} — content landed on the "
            f"wrong side (rotation/composition bug, not AA)"
        )


@pytest.mark.parametrize("label", list(_CASES), ids=list(_CASES))
def test_page_render_integration_emptiness_pinned(
    label: str, tmp_path: Path
) -> None:
    """Oracle-free pin of the documented PDFBox 3.0.7 emptiness verdict — runs
    everywhere (no Java needed) so the whole-page composition stays green in CI
    without the live jar. A flip here is a composition regression, not AA."""
    _content, _rect, _rotation, dpi = _CASES[label]
    fixture = _build(label, tmp_path / f"{label}.pdf")
    with PDDocument.load(fixture) as doc:
        img = PDFRenderer(doc).render_image_with_dpi(0, dpi)
    painted, _bbox, _quad = _painted_facts(img)
    expect_painted = _EXPECT_PAINTED[label]
    assert (painted > 0) == expect_painted, (
        f"{label}: expected painted={expect_painted} but got {painted}px "
        f"(PDFBox 3.0.7 reference)."
    )


@pytest.mark.parametrize(
    "label,expect_w,expect_h",
    [
        ("combined_dpi72", 200, 300),
        ("combined_dpi150", 416, 625),
        ("combined_dpi300", 833, 1250),
        ("combined_rot90", 300, 200),
        ("combined_rot180", 200, 300),
        ("combined_rot270", 300, 200),
        ("combined_rot90_dpi150", 625, 416),
        ("square_rot90", 200, 200),
    ],
)
def test_page_render_dimensions_pinned(
    label: str, expect_w: int, expect_h: int, tmp_path: Path
) -> None:
    """Oracle-free pin of the PDFBox 3.0.7 DPI/rotation pixel-dimension
    arithmetic (``pts * dpi/72`` float floor; 90/270 swap W/H). A regression in
    the renderer's geometry flips a dimension here without any Java needed."""
    _content, _rect, _rotation, dpi = _CASES[label]
    fixture = _build(label, tmp_path / f"{label}.pdf")
    with PDDocument.load(fixture) as doc:
        img = PDFRenderer(doc).render_image_with_dpi(0, dpi)
    assert img.size == (expect_w, expect_h), (
        f"{label}: dims {img.size} != expected ({expect_w}, {expect_h})"
    )


@requires_oracle
def test_rotation_places_content_like_pdfbox(tmp_path: Path) -> None:
    """Direct integration pin: the asymmetric combined page (text top-left,
    filled rect bottom-left) must, after a 90-degree ``/Rotate``, place its
    dominant paint in the SAME quadrant PDFBox does. Guards specifically
    against the renderer rotating content the wrong direction."""
    _content, _rect, _rotation, dpi = _CASES["combined_rot90"]
    fixture = _build("combined_rot90", tmp_path / "rot90.pdf")
    (jw, jh), java_painted, _jbox, java_quad = _oracle_facts(fixture, dpi)
    assert java_painted > 0, "oracle sanity: PDFBox should paint the page"
    assert (jw, jh) == (300, 200), "oracle sanity: 90 rotation swaps W/H"

    with PDDocument.load(fixture) as doc:
        img = PDFRenderer(doc).render_image_with_dpi(0, dpi)
    py_painted, _pbox, py_quad = _painted_facts(img)
    assert py_painted > 0, "rotation regression: pypdfbox rendered nothing"
    java_dom = _dominant_quadrant(java_quad)
    py_dom = _dominant_quadrant(py_quad)
    if java_dom is not None:
        assert py_dom == java_dom, (
            f"90-rotation places content in {py_dom}{py_quad}; PDFBox uses "
            f"{java_dom}{java_quad}"
        )
