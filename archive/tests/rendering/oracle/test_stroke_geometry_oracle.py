"""Live PDFBox differential parity for **thick-stroke geometry**: line cap
(``J`` 0 butt / 1 round / 2 projecting-square), line join (``j`` 0 miter /
1 round / 2 bevel), miter limit (``M``), and dash patterns
(``d [array] phase``) — PDF 32000-1 §8.4.3.3–§8.4.3.6.

These are the stroke style attributes that only become visible on *thick*
lines and at path vertices / endpoints. They map onto skia's
``Paint.Cap`` / ``Paint.Join`` / ``StrokeMiter`` / ``DashPathEffect`` in
``pypdfbox/rendering/_aggdraw_compat.py``; this surface pins that mapping
against Java PDFBox's Java2D ``BasicStroke`` rendering.

Distinct from ``test_dash_phase_oracle.py`` (which isolates the ``d`` *phase*
operand on a single horizontal line): this surface pins the *cap*, *join*,
and *miter-limit* geometry — endpoint shape, vertex shape, and the
miter→bevel fallback — plus a multi-dash regression pin on an
``L``-shaped path so caps and joins interact with the dash segmentation.

Fixtures (one-page PDFs synthesised in-memory, thick black strokes on white):

* **cap_butt / cap_round / cap_square** — a short thick horizontal segment
  whose endpoint cap shape differs. Butt stops flush at the endpoint; round
  bulges a semicircle; square projects half-a-line-width past the endpoint.
* **join_miter / join_round / join_bevel** — a sharp ``>``-shaped vertex
  (two segments meeting at an acute angle) where the join shape diverges:
  miter spikes out, round arcs, bevel cuts the corner flat.
* **miter_clipped** — the same acute vertex with ``M 1.0`` (miter limit below
  the join's miter ratio), forcing the spec-mandated fallback to a bevel join
  even though ``j 0`` (miter) is selected.
* **dash_caps_joins** — a thick dashed ``L`` path (``[12 8] 0 d``, round caps
  + round joins) exercising cap+join+dash together as a regression pin.

Pixel-EXACT parity is impossible (Java2D vs skia AA — see ``CHANGES.md`` /
``test_render_oracle.py``); we compare the proven coarse fingerprint: exact
rendered dimensions plus a 16x16 average-luminance grid, gated at
``MAD < 6`` / ``MAXDIFF < 60`` against
``oracle/probes/StrokeGeometryProbe.java`` (72 DPI, RenderProbe luminance
math). A guard test proves butt vs projecting-square caps produce a
materially different raster, so the gate would catch a dropped cap style.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from pypdfbox.cos import COSName, COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.pd_resources import PDResources
from pypdfbox.rendering import PDFRenderer
from tests.oracle.harness import requires_oracle, run_probe_text

_GRID = 16
# Same whole-page render gate as test_dash_phase_oracle.py /
# test_render_oracle.py — comfortably above the Java2D-vs-skia AA ceiling yet
# well below the gross-failure floor (a dropped cap/join/miter style or an
# ignored dash all diverge far past this).
_MAD_TOLERANCE = 6.0
_MAXDIFF_TOLERANCE = 60

_PAGE = 120.0  # square page (== px at 72 DPI)


def _content_for(label: str) -> bytes:
    """Content stream for one stroke-geometry fixture. Thick black strokes
    (12 user-space units wide) on the default white page so the cap/join
    geometry occupies several fingerprint cells."""
    if label == "cap_butt":
        # Short thick horizontal segment, butt cap (default, J 0).
        return b"12 w 0 J 0 0 0 RG\n40 60 m 80 60 l S\n"
    if label == "cap_round":
        return b"12 w 1 J 0 0 0 RG\n40 60 m 80 60 l S\n"
    if label == "cap_square":
        # Projecting-square cap extends 6 units (half width) past each end.
        return b"12 w 2 J 0 0 0 RG\n40 60 m 80 60 l S\n"
    if label == "join_miter":
        # Acute '>' vertex at (90,60); miter join spikes the corner out.
        return b"12 w 0 j 10 M 0 0 0 RG\n30 30 m 90 60 l 30 90 l S\n"
    if label == "join_round":
        return b"12 w 1 j 0 0 0 RG\n30 30 m 90 60 l 30 90 l S\n"
    if label == "join_bevel":
        return b"12 w 2 j 0 0 0 RG\n30 30 m 90 60 l 30 90 l S\n"
    if label == "miter_clipped":
        # Miter join selected (j 0) but miter limit 1.0 < the vertex's miter
        # ratio, so the spec forces a bevel fallback at the acute corner.
        return b"12 w 0 j 1 M 0 0 0 RG\n30 30 m 90 60 l 30 90 l S\n"
    if label == "dash_caps_joins":
        # Thick dashed 'L' path: round caps + round joins + a [12 8] dash.
        return b"10 w 1 J 1 j [12 8] 0 d 0 0 0 RG\n30 30 m 30 90 l 90 90 l S\n"
    raise ValueError(label)  # pragma: no cover


def _build(label: str, out: Path) -> Path:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, _PAGE, _PAGE))
    page.set_resources(PDResources())
    doc.add_page(page)
    stream = COSStream()
    stream.set_raw_data(_content_for(label))
    page.get_cos_object().set_item(COSName.CONTENTS, stream)
    doc.save(str(out))
    doc.close()
    return out


_LABELS = [
    "cap_butt",
    "cap_round",
    "cap_square",
    "join_miter",
    "join_round",
    "join_bevel",
    "miter_clipped",
    "dash_caps_joins",
]


# ---------------------------------------------------------------------------
# fingerprint helpers — must mirror StrokeGeometryProbe.java's cell mapping
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
    """Run StrokeGeometryProbe on page 0 and parse its (dims, 16x16 grid).
    The probe emits the grid comma-separated (see the probe header)."""
    lines = run_probe_text("StrokeGeometryProbe", str(fixture), "0").splitlines()
    width, height = (int(v) for v in lines[0].split())
    grid = [int(v) for v in lines[1].split(",")]
    assert len(grid) == _GRID * _GRID
    return (width, height), grid


def _mad_maxdiff(a: list[int], b: list[int]) -> tuple[float, int]:
    diffs = [abs(x - y) for x, y in zip(a, b, strict=True)]
    return sum(diffs) / len(diffs), max(diffs)


# ---------------------------------------------------------------------------
# differential tests
# ---------------------------------------------------------------------------


@requires_oracle
@pytest.mark.parametrize("label", _LABELS, ids=_LABELS)
def test_stroke_geometry_matches_pdfbox(label: str, tmp_path: Path) -> None:
    """Each cap / join / miter-limit / dash variant must match Java PDFBox's
    render of the same fixture within the 16x16 fingerprint gate."""
    fixture = _build(label, tmp_path / f"{label}.pdf")

    (java_w, java_h), java_grid = _oracle_signature(fixture)

    with PDDocument.load(fixture) as doc:
        img = PDFRenderer(doc).render_image_with_dpi(0, 72.0)
    py_w, py_h = img.size
    py_grid = _grid_from_image(img)

    # (a) Exact pixel dimensions — a mismatch is a real bug, not AA.
    assert (py_w, py_h) == (java_w, java_h), (
        f"{label}: rendered dimensions diverge from PDFBox: "
        f"pypdfbox={py_w}x{py_h} java={java_w}x{java_h}"
    )

    # (b) Perceptual grid parity within tolerance.
    mad, maxdiff = _mad_maxdiff(java_grid, py_grid)
    assert mad < _MAD_TOLERANCE, (
        f"{label}: mean abs cell diff {mad:.2f} >= {_MAD_TOLERANCE} "
        f"(maxdiff={maxdiff}) — stroke geometry mis-applied, not just AA"
    )
    assert maxdiff < _MAXDIFF_TOLERANCE, (
        f"{label}: worst cell diff {maxdiff} >= {_MAXDIFF_TOLERANCE} "
        f"(mad={mad:.2f}) — a region diverges far beyond anti-aliasing"
    )


@requires_oracle
def test_butt_vs_square_caps_differ_materially(tmp_path: Path) -> None:
    """Guard the gate: butt and projecting-square caps on the SAME segment
    must produce materially different rasters (the square cap projects half
    a line-width past each endpoint). If a renderer dropped the cap style,
    both would render identically and this guard would catch it — proving
    the per-fixture gate is detecting cap geometry, not passing any
    content-bearing line."""
    butt = _build("cap_butt", tmp_path / "cap_butt.pdf")
    square = _build("cap_square", tmp_path / "cap_square.pdf")

    with PDDocument.load(butt) as doc:
        butt_grid = _grid_from_image(
            PDFRenderer(doc).render_image_with_dpi(0, 72.0)
        )
    with PDDocument.load(square) as doc:
        square_grid = _grid_from_image(
            PDFRenderer(doc).render_image_with_dpi(0, 72.0)
        )

    # The square cap projects 6px (half the 12-unit width) past each end of a
    # 40-unit segment on a 120x120 page, so the difference is localised to the
    # endpoint cells; averaged over the whole 16x16 grid that is a few units of
    # MAD — but the per-cell MAXDIFF at the projecting ends is large. Assert on
    # MAXDIFF so the guard tracks the local cap geometry, not the whole-page
    # average (two identical renders score ~0 here).
    mad, maxdiff = _mad_maxdiff(butt_grid, square_grid)
    assert maxdiff >= _MAXDIFF_TOLERANCE, (
        "butt vs square caps render too similarly "
        f"(mad={mad:.2f}, maxdiff={maxdiff}) — the cap style would not be "
        "caught by the gate"
    )


@requires_oracle
def test_miter_limit_clips_to_bevel(tmp_path: Path) -> None:
    """Direct proof the miter limit is honoured: the same acute vertex with
    ``M 1.0`` (below the join's miter ratio) must render *differently* from
    the unclipped ``M 10`` miter join — the spike is clipped to a bevel. A
    renderer that ignores the miter limit renders both identically."""
    clipped = _build("miter_clipped", tmp_path / "miter_clipped.pdf")
    miter = _build("join_miter", tmp_path / "join_miter.pdf")

    with PDDocument.load(clipped) as doc:
        clipped_grid = _grid_from_image(
            PDFRenderer(doc).render_image_with_dpi(0, 72.0)
        )
    with PDDocument.load(miter) as doc:
        miter_grid = _grid_from_image(
            PDFRenderer(doc).render_image_with_dpi(0, 72.0)
        )

    mad, maxdiff = _mad_maxdiff(clipped_grid, miter_grid)
    assert maxdiff >= 20, (
        "miter-limit-clipped vertex renders identically to the unclipped "
        f"miter join (maxdiff={maxdiff}) — the miter limit appears ignored"
    )
