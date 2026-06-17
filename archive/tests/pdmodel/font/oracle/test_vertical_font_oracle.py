"""Live Apache PDFBox differential parity for Type0 *vertical writing mode*.

Pins pypdfbox's WMode-1 (vertical) composite-font metrics against Apache
PDFBox 3.0.7. The surface under test is the vertical-writing API on
``PDType0Font`` and its descendant ``PDCIDFont``:

* ``is_vertical`` — WMode-1 detection from the ``/Encoding`` CMap (``Identity-V``).
* ``get_position_vector(code)`` — the position vector ``(v_x, v_y)`` in em,
  the descendant's ``/W2`` triple ``(_, v_x, v_y)`` (or the default
  ``(width/2, DW2[0])``) scaled by ``-1/1000``.
* ``get_displacement(code)`` — for a vertical font the displacement vector is
  ``(0, w1y/1000)`` where ``w1y`` is the descendant's vertical displacement
  vector y (``/W2`` ``w1y``, falling back to ``/DW2``'s displacement-vector-y,
  default ``-1000``).
* ``PDCIDFont.get_vertical_displacement_vector_y(code)`` — the raw 1/1000-em
  ``w1y`` metric, with the ``/DW2`` fallback.

No vertical (``Identity-V`` / ``/WMode``) fixture ships in ``tests/fixtures``,
so the test *builds* two Type0 fonts in-process from the bundled
LiberationSans TTF (already provenance-tracked) via
``PDType0Font.load_vertical`` (``/Encoding /Identity-V``):

* **DW2-default** — no ``/W2`` and no ``/DW2``, exercising the spec defaults
  (position-vector-y ``880``, displacement-vector-y ``-1000``).
* **explicit-W2** — an explicit ``/DW2 [900 -1100]`` plus a ``/W2`` array
  using both the form-1 (``c [w1y vx vy ...]``) and form-2 (``c1 c2 w1y vx
  vy``) layouts, exercising covered CIDs and the per-CID fallback.

Each saved PDF is loaded by both engines and the per-code metric lines are
compared exactly (floats normalised to 6 decimals).

Divergence history:
  * Wave 1428 found ``PDType0Font.get_displacement`` (vertical branch)
    returned ``(0, descendant.get_height(cid)/1000)`` — the glyph's *extent*
    with a ``0.0`` fallback for un-covered CIDs — instead of upstream's
    ``(0, descendant.getVerticalDisplacementVectorY(code)/1000)``, which is
    the ``/W2`` ``w1y`` metric with the ``/DW2`` displacement-vector-y
    fallback (default ``-1000``). Every vertical displacement was wrong: CIDs
    in ``/W2`` returned the glyph extent rather than ``w1y``, and CIDs outside
    ``/W2`` returned ``0`` rather than ``-1.0``. Fixed in
    ``PDType0Font.get_displacement``. See CHANGES.md.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from pypdfbox.cos import COSArray, COSFloat, COSInteger, COSName
from pypdfbox.pdmodel import PDPage, PDRectangle
from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream
from tests.oracle.harness import requires_oracle, run_probe_text

_TTF = (
    Path(__file__).resolve().parents[4]
    / "pypdfbox"
    / "resources"
    / "ttf"
    / "LiberationSans-Regular.ttf"
)

# Codes probed for every font — kept in lockstep with VerticalFontProbe.CODES.
# Mix of low CIDs (covered by /W2 in the explicit case), CID 0 (.notdef), and
# high CIDs that fall back to the /DW2 defaults.
_CODES = (0, 1, 2, 3, 5, 10, 100, 60000, 65535)


def _f(v: float) -> str:
    """Normalise a float the same way VerticalFontProbe.f does."""
    if v == 0.0:
        v = 0.0
    return f"{v:.6f}"


def _cf(v: float) -> COSFloat:
    return COSFloat(float(v))


def _build_vertical_pdf(*, explicit_w2: bool) -> bytes:
    """Build a single-page PDF embedding LiberationSans as a vertical
    (``/Identity-V``) Type0 font, optionally with explicit ``/W2`` + ``/DW2``.
    """
    doc = PDDocument()
    page = PDPage(PDRectangle.LETTER)
    doc.add_page(page)
    with _TTF.open("rb") as fh:
        font = PDType0Font.load_vertical(doc, fh, False)
    descendant = font.get_descendant_font()
    assert descendant is not None
    if explicit_w2:
        cos = descendant.get_cos_object()
        # /DW2 = [position_vector_y displacement_vector_y]; non-default values.
        dw2 = COSArray()
        dw2.add(COSInteger.get(900))
        dw2.add(COSInteger.get(-1100))
        cos.set_item(COSName.get_pdf_name("DW2"), dw2)
        # /W2 — form 1 (c [w1y vx vy ...]) for CIDs 1,2,3 and form 2
        # (c1 c2 w1y vx vy) for the range 5..10.
        w2 = COSArray()
        w2.add(COSInteger.get(1))
        inner = COSArray()
        for triple in ((-1000, 250, 880), (-980, 260, 870), (-1020, 240, 890)):
            for x in triple:
                inner.add(_cf(x))
        w2.add(inner)
        w2.add(COSInteger.get(5))
        w2.add(COSInteger.get(10))
        for x in (-1050, 300, 860):
            w2.add(_cf(x))
        cos.set_item(COSName.get_pdf_name("W2"), w2)
        descendant.clear_widths_cache()
    encoded = font.encode("AB")
    with PDPageContentStream(doc, page) as cs:
        cs.begin_text()
        cs.set_font(font, 14)
        cs.new_line_at_offset(50, 700)
        cs.show_text(encoded)
        cs.end_text()
    sink = io.BytesIO()
    doc.save(sink)
    doc.close()
    return sink.getvalue()


def _py_vertical_metrics(pdf_path: Path) -> str:
    """Reconstruct the VerticalFontProbe output from pypdfbox, line-for-line."""
    lines: list[str] = []
    doc = PDDocument.load(pdf_path)
    try:
        for page_index, page in enumerate(doc.get_pages()):
            res = page.get_resources()
            if res is None:
                continue
            for name in res.get_font_names():
                try:
                    font = res.get_font(name)
                except Exception:
                    continue
                if not isinstance(font, PDType0Font):
                    continue
                key = name.name if hasattr(name, "name") else str(name)
                descendant = font.get_descendant_font()
                lines.append(
                    f"FONT\t{page_index}\t{key}\t{font.get_name()}\t"
                    f"{'true' if font.is_vertical() else 'false'}"
                )
                for code in _CODES:
                    cid = font.code_to_cid(code)
                    pos = font.get_position_vector(code)
                    disp = font.get_displacement(code)
                    v_y = (
                        descendant.get_vertical_displacement_vector_y(code)
                        if descendant is not None
                        else 0.0
                    )
                    lines.append(
                        f"CODE\t{page_index}\t{key}\t{code}\t{cid}\t"
                        f"{_f(pos[0])}\t{_f(pos[1])}\t"
                        f"{_f(disp[0])}\t{_f(disp[1])}\t{_f(v_y)}"
                    )
    finally:
        doc.close()
    return "\n".join(lines) + ("\n" if lines else "")


def _assert_parity(pdf_bytes: bytes, tmp_path: Path, label: str) -> list[str]:
    pdf_path = tmp_path / f"vertical_{label}.pdf"
    pdf_path.write_bytes(pdf_bytes)
    java = run_probe_text("VerticalFontProbe", str(pdf_path)).splitlines()
    py = _py_vertical_metrics(pdf_path).splitlines()
    assert len(java) == len(py), (
        f"line-count mismatch for {label}: java={len(java)} py={len(py)}"
    )
    diffs = [
        f"  line {i}: java={j!r} py={p!r}"
        for i, (j, p) in enumerate(zip(java, py, strict=True))
        if j != p
    ]
    assert not diffs, (
        f"vertical-font metric parity broken for {label}:\n" + "\n".join(diffs[:40])
    )
    return java


@requires_oracle
def test_vertical_dw2_default_matches_pdfbox(tmp_path: Path) -> None:
    """A vertical Type0 font with no ``/W2`` / ``/DW2`` must match PDFBox.

    Exercises the spec-default vertical metrics: position-vector-y ``880``
    (``-0.880`` in em after the ``-1/1000`` scale) and displacement-vector-y
    ``-1000`` (``-1.0`` in em). Every CID falls back to these defaults, and the
    position vector's ``v_x`` is ``width/2`` per glyph.
    """
    java = _assert_parity(
        _build_vertical_pdf(explicit_w2=False), tmp_path, "dw2_default"
    )
    # Sanity: the font is reported vertical and the default displacement-y is
    # the spec -1000/1000 = -1.0 (not 0.0 — the wave-1428 regression).
    assert any(line.endswith("\ttrue") for line in java)
    code1 = next(ln for ln in java if ln.startswith("CODE\t0\tF1\t1\t"))
    assert code1.split("\t")[8] == "-1.000000", code1


@requires_oracle
def test_vertical_explicit_w2_matches_pdfbox(tmp_path: Path) -> None:
    """A vertical Type0 font with explicit ``/W2`` + ``/DW2`` must match PDFBox.

    Exercises both ``/W2`` layouts (form 1 ``c [w1y vx vy ...]`` and form 2
    ``c1 c2 w1y vx vy``), CIDs covered by the table, and CIDs outside it that
    fall back to the explicit ``/DW2 [900 -1100]`` defaults.
    """
    java = _assert_parity(
        _build_vertical_pdf(explicit_w2=True), tmp_path, "explicit_w2"
    )
    # A covered CID (1) must use its /W2 w1y (-1000 -> -1.0), and an uncovered
    # CID (100) must use the explicit /DW2 displacement-y (-1100 -> -1.1).
    code1 = next(ln for ln in java if ln.startswith("CODE\t0\tF1\t1\t"))
    assert code1.split("\t")[8] == "-1.000000", code1
    code100 = next(ln for ln in java if ln.startswith("CODE\t0\tF1\t100\t"))
    assert code100.split("\t")[8] == "-1.100000", code100


def test_get_displacement_uses_vertical_displacement_not_glyph_height(
    tmp_path: Path,
) -> None:
    """Regression pin for the wave-1428 fix (no oracle needed).

    ``PDType0Font.get_displacement`` on a vertical font must return the
    descendant's vertical displacement vector y (``/W2`` ``w1y`` with the
    ``/DW2`` fallback, default ``-1000``), *not* ``get_height`` (the glyph
    extent, which returned ``0.0`` for un-covered CIDs). The displacement-x
    component must always be ``0`` for a vertical font.
    """
    pdf_path = tmp_path / "regression.pdf"
    pdf_path.write_bytes(_build_vertical_pdf(explicit_w2=True))
    doc = PDDocument.load(pdf_path)
    try:
        page = next(iter(doc.get_pages()))
        res = page.get_resources()
        assert res is not None
        font = next(
            res.get_font(n)
            for n in res.get_font_names()
            if isinstance(res.get_font(n), PDType0Font)
        )
        assert font.is_vertical()
        descendant = font.get_descendant_font()
        assert descendant is not None
        # Covered CID 1: w1y == -1000 -> -1.0; not the glyph extent.
        dx, dy = font.get_displacement(1)
        assert dx == 0.0
        assert dy == pytest.approx(-1.0)
        assert dy == pytest.approx(
            descendant.get_vertical_displacement_vector_y(1) / 1000.0
        )
        # Un-covered CID 100: falls back to explicit /DW2 displacement-y
        # (-1100 -> -1.1), and must NOT be 0.0 (the pre-fix value).
        dx100, dy100 = font.get_displacement(100)
        assert dx100 == 0.0
        assert dy100 == pytest.approx(-1.1)
        assert dy100 != 0.0
    finally:
        doc.close()


def test_default_position_vector_components(tmp_path: Path) -> None:
    """Spec-default ``/DW2`` position/displacement vector y (no oracle needed).

    Without ``/DW2`` the descendant returns position-vector-y ``880`` and
    displacement-vector-y ``-1000``; the position vector for an un-covered CID
    is ``(width/2, 880)`` and ``get_position_vector`` scales it by ``-1/1000``.
    """
    pdf_path = tmp_path / "defaults.pdf"
    pdf_path.write_bytes(_build_vertical_pdf(explicit_w2=False))
    doc = PDDocument.load(pdf_path)
    try:
        page = next(iter(doc.get_pages()))
        res = page.get_resources()
        assert res is not None
        font = next(
            res.get_font(n)
            for n in res.get_font_names()
            if isinstance(res.get_font(n), PDType0Font)
        )
        descendant = font.get_descendant_font()
        assert descendant is not None
        assert descendant.get_dw2_position_vector_y() == pytest.approx(880.0)
        assert descendant.get_dw2_displacement_vector_y() == pytest.approx(-1000.0)
        # Position vector y is the scaled -880/1000 = -0.88 for any CID.
        _, pv_y = font.get_position_vector(1)
        assert pv_y == pytest.approx(-0.88)
        # Displacement-y default is -1.0 (the regression value).
        _, dy = font.get_displacement(1)
        assert dy == pytest.approx(-1.0)
    finally:
        doc.close()
