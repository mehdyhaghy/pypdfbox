"""Live PDFBox differential parity for **rotated / sheared text** painted via
the text-matrix operator ``Tm`` (PDF 32000-1 §9.4.2 / §9.4.4).

The text matrix ``Tm`` is what positions *and orients* every subsequent glyph.
A renderer that honours only the translation components (e / f) but ignores the
linear part (a / b / c / d) will still paint the glyphs but they end up
*upright and horizontal*, not rotated or sheared. The classic shape of this
bug:

* ``Tm 0.7071 0.7071 -0.7071 0.7071 e f`` (45° rotation) — glyphs lay flat on
  the baseline, no diagonal stem;
* ``Tm 0 1 -1 0 e f`` (90° rotation, vertical-looking) — glyphs stay
  horizontal instead of tipping onto their side;
* ``Tm 1 0 0.5 1 e f`` (italic-like shear) — glyphs stand straight up instead
  of slanting.

All three forms exercise the same path: ``_show_string`` reads the bytes,
``_draw_glyph`` composes the per-glyph text-rendering matrix
``text_local * Tm * full_ctm`` and feeds it to the glyph fill. If ``Tm`` were
applied only to the *position* (advance) and not woven into the per-glyph CTM,
the glyph outlines would land at the rotated origin but face the wrong way and
the rendered fingerprint would diverge sharply from Apache PDFBox's.

Comparison reuses ``oracle/probes/RenderProbe.java`` (the page's exact pixel
dimensions + a 16x16 average-luminance grid). The MAD<6 / MAXDIFF<60 gate is
the same one calibrated in wave 1408 against PDFBox 3.0.7 at 72 DPI for the
other render oracles. Measured here the rotated/sheared renders land at
MAD ~0.03 / MAXDIFF <= 2 (essentially Java2D-vs-Pillow anti-aliasing only).

Extra guards prove ``Tm`` actually transforms the glyph *outlines*, not just
the origin:

* the rotated/sheared render's 16x16 grid diverges materially from a
  non-rotated baseline (MAXDIFF > 60 with the TTF fixture's real glyph
  shapes) — a renderer that ignored the linear part of ``Tm`` would render
  identically to the baseline and fail this guard;
* the 90°-rotated run's *painted bounding box* is taller than it is wide
  (the opposite of the horizontal baseline) — a renderer that left the
  outlines upright would produce a wide-and-short bbox like the baseline.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from PIL import Image

from pypdfbox.cos.cos_name import COSName
from pypdfbox.cos.cos_stream import COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font
from pypdfbox.pdmodel.pd_resources import PDResources
from pypdfbox.rendering import PDFRenderer
from tests.oracle.harness import requires_oracle, run_probe_text

_GRID = 16
# Same gate the other whole-page render oracles use (wave 1408 calibration).
_MAD_TOLERANCE = 6.0
_MAXDIFF_TOLERANCE = 60

_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "fontbox" / "ttf"

# Square page so a 45/90 rotation never clips off the canvas.
_PW, _PH, _FS = 240.0, 240.0, 40

# The CID-encoded byte string for "ABCDE" through ``Identity-H`` (each glyph
# is a 2-byte CID; for LiberationSans GID and code happen to coincide for
# these ASCII letters but the cmap drives the actual lookup).
_ABCDE_CIDS = b"<00410042004300440045>"

# A baseline (identity Tm) and three transformed variants. The translate part
# (e / f) of each Tm is chosen so the painted run still falls on the page.
_CONTENT: dict[str, bytes] = {
    # Identity Tm — straight horizontal "ABCDE" near the page centre.
    "baseline": b"BT\n/F1 %d Tf\n1 0 0 1 20 120 Tm\n%s Tj\nET\n"
    % (_FS, _ABCDE_CIDS),
    # 45° rotation — Tm = [cos sin -sin cos e f] with cos=sin=0.7071.
    "rot45": b"BT\n/F1 %d Tf\n0.7071 0.7071 -0.7071 0.7071 30 30 Tm\n%s Tj\nET\n"
    % (_FS, _ABCDE_CIDS),
    # 90° rotation — Tm = [0 1 -1 0 e f]: glyphs tip onto their right side.
    "rot90": b"BT\n/F1 %d Tf\n0 1 -1 0 130 30 Tm\n%s Tj\nET\n"
    % (_FS, _ABCDE_CIDS),
    # Italic-like shear — Tm = [1 0 0.5 1 e f]: x-skew by tan(~27°).
    "shear": b"BT\n/F1 %d Tf\n1 0 0.5 1 20 30 Tm\n%s Tj\nET\n"
    % (_FS, _ABCDE_CIDS),
}


def _build(out: Path, content: bytes) -> Path:
    """Build a single-page PDF embedding LiberationSans via ``PDType0Font``
    (``Identity-H``) and the supplied ``content`` as the page stream."""
    ttf = (_FIXTURES / "LiberationSans-Regular.ttf").read_bytes()
    doc = PDDocument()
    try:
        while doc.get_number_of_pages() > 0:
            doc.remove_page(0)
        page = PDPage(PDRectangle(0.0, 0.0, _PW, _PH))
        doc.add_page(page)

        font = PDType0Font.load(doc, io.BytesIO(ttf))
        res = PDResources()
        res.put(COSName.get_pdf_name("F1"), font)
        page.set_resources(res)

        cs = COSStream()
        cs.set_data(content)
        page.set_contents(cs)
        doc.save(str(out))
    finally:
        doc.close()
    return out


# ---------------------------------------------------------------------------
# fingerprint helpers — must mirror RenderProbe.java's cell mapping exactly
# ---------------------------------------------------------------------------


def _grid_from_image(img: Image.Image) -> list[int]:
    gray = img.convert("L")
    width, height = gray.size
    pixels = gray.load()
    total = [0] * (_GRID * _GRID)
    count = [0] * (_GRID * _GRID)
    for y in range(height):
        cy = min(_GRID - 1, y * _GRID // height)
        for x in range(width):
            cx = min(_GRID - 1, x * _GRID // width)
            idx = cy * _GRID + cx
            total[idx] += pixels[x, y]
            count[idx] += 1
    return [
        round(total[i] / count[i]) if count[i] else 255
        for i in range(_GRID * _GRID)
    ]


def _oracle_signature(fixture: Path) -> tuple[tuple[int, int], list[int]]:
    lines = run_probe_text("RenderProbe", str(fixture), "0").splitlines()
    width, height = (int(v) for v in lines[0].split())
    grid = [int(v) for v in lines[1].split()]
    assert len(grid) == _GRID * _GRID
    return (width, height), grid


def _mad_maxdiff(a: list[int], b: list[int]) -> tuple[float, int]:
    diffs = [abs(x - y) for x, y in zip(a, b, strict=True)]
    return sum(diffs) / len(diffs), max(diffs)


def _py_render(fixture: Path) -> Image.Image:
    with PDDocument.load(fixture) as doc:
        return PDFRenderer(doc).render_image_with_dpi(0, 72.0)


def _py_grid(fixture: Path) -> tuple[tuple[int, int], list[int]]:
    img = _py_render(fixture)
    return img.size, _grid_from_image(img)


def _dark_bbox(img: Image.Image, threshold: int = 128) -> tuple[int, int]:
    """Return (width, height) of the bounding box of pixels darker than
    ``threshold`` — proxy for the painted run's geometric footprint."""
    gray = img.convert("L")
    width, height = gray.size
    pixels = gray.load()
    xs: list[int] = []
    ys: list[int] = []
    for y in range(height):
        for x in range(width):
            if pixels[x, y] < threshold:
                xs.append(x)
                ys.append(y)
    if not xs:
        return (0, 0)
    return (max(xs) - min(xs) + 1, max(ys) - min(ys) + 1)


# ---------------------------------------------------------------------------
# differential tests
# ---------------------------------------------------------------------------

_LABELS = ["baseline", "rot45", "rot90", "shear"]


@requires_oracle
@pytest.mark.parametrize("label", _LABELS, ids=_LABELS)
def test_tm_rotation_and_shear_match_pdfbox(label: str, tmp_path: Path) -> None:
    """Each ``Tm`` rotation / shear renders to identically positioned (within
    the AA tolerance) glyphs as Apache PDFBox 3.0.7."""
    fixture = _build(tmp_path / f"{label}.pdf", _CONTENT[label])
    (java_w, java_h), java_grid = _oracle_signature(fixture)
    (py_w, py_h), py_grid = _py_grid(fixture)

    # (a) Exact pixel dimensions — a mismatch is a real bug, not AA.
    assert (py_w, py_h) == (java_w, java_h), (
        f"{label}: rendered dimensions diverge from PDFBox: "
        f"pypdfbox={py_w}x{py_h} java={java_w}x{java_h}"
    )

    # (b) Perceptual grid parity within tolerance — catches glyphs painted
    #     upright when the matrix asked for rotation/shear.
    mad, maxdiff = _mad_maxdiff(java_grid, py_grid)
    assert mad < _MAD_TOLERANCE, (
        f"{label}: mean abs cell diff {mad:.2f} >= {_MAD_TOLERANCE} "
        f"(maxdiff={maxdiff}) — glyph outlines diverge grossly, not AA"
    )
    assert maxdiff < _MAXDIFF_TOLERANCE, (
        f"{label}: worst cell diff {maxdiff} >= {_MAXDIFF_TOLERANCE} "
        f"(mad={mad:.2f}) — a region diverges far beyond anti-aliasing"
    )


@requires_oracle
@pytest.mark.parametrize(
    "label", ["rot45", "rot90", "shear"], ids=["rot45", "rot90", "shear"]
)
def test_tm_linear_part_changes_painted_glyphs(
    label: str, tmp_path: Path
) -> None:
    """Each transformed ``Tm`` must materially change the painted glyphs vs
    the identity-``Tm`` baseline. A renderer that honoured only the
    translation (e / f) part of ``Tm`` and ignored a / b / c / d would
    render identically to the baseline and fail here."""
    variant = _build(tmp_path / f"{label}.pdf", _CONTENT[label])
    reference = _build(tmp_path / "baseline.pdf", _CONTENT["baseline"])

    _vdims, variant_grid = _py_grid(variant)
    _rdims, reference_grid = _py_grid(reference)
    _mad, maxdiff = _mad_maxdiff(variant_grid, reference_grid)
    assert maxdiff > _MAXDIFF_TOLERANCE, (
        f"{label}: painted output diverges from the identity-Tm baseline by "
        f"only maxdiff={maxdiff} cells (<= {_MAXDIFF_TOLERANCE}) — the "
        f"linear part of Tm is not being applied to the glyph outlines"
    )


@requires_oracle
def test_tm_90deg_rotates_glyph_outlines(tmp_path: Path) -> None:
    """A 90° ``Tm`` rotation must rotate the *glyph outlines*, not just the
    advance: the painted run's bounding box flips from wide-and-short
    (horizontal baseline) to tall-and-narrow (rotated column). A renderer
    that translated the origin but left the outlines upright would still
    produce a wide-and-short bbox and fail this guard."""
    baseline = _build(tmp_path / "baseline.pdf", _CONTENT["baseline"])
    rotated = _build(tmp_path / "rot90.pdf", _CONTENT["rot90"])

    base_w, base_h = _dark_bbox(_py_render(baseline))
    rot_w, rot_h = _dark_bbox(_py_render(rotated))

    # Baseline run is clearly horizontal: wider than tall by a large margin.
    assert base_w > base_h * 2, (
        f"baseline bbox is not horizontally elongated: w={base_w} h={base_h}"
    )
    # 90°-rotated run must flip the aspect: taller than wide by the same
    # rough margin. A renderer that ignored the linear part of Tm would
    # keep the baseline's wide-and-short shape and fail this assertion.
    assert rot_h > rot_w * 2, (
        f"Tm 90° did not rotate the glyph outlines: rotated bbox is "
        f"w={rot_w} h={rot_h} (expected h > w*2 like a vertical column)"
    )

    # Cross-check the rotated render against PDFBox for completeness.
    (java_dims), java_grid = _oracle_signature(rotated)
    (py_dims), py_grid = _py_grid(rotated)
    assert py_dims == java_dims
    mad, maxdiff = _mad_maxdiff(java_grid, py_grid)
    assert mad < _MAD_TOLERANCE and maxdiff < _MAXDIFF_TOLERANCE, (
        f"Tm 90° diverges from PDFBox: mad={mad:.2f} maxdiff={maxdiff}"
    )
