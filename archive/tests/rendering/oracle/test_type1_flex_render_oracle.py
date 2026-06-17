"""Live PDFBox differential parity for embedded Type 1 (PFB / ``/FontFile``)
glyphs whose charstrings use **curves + the flex / hint-replacement OtherSubrs
machinery** (``callsubr`` into the four standard subroutines, ``callothersubr``
OtherSubrs 0/1/2/3, and ``div``).

Wave 1444. Companion to:

* ``tests/rendering/oracle/test_type1_glyph_render_oracle.py`` — simple Type 1
  glyph paint (``DemoType1.pfb`` straight-line A/B/C boxes), and
* ``tests/rendering/oracle/test_type1_seac_render_oracle.py`` — the Type 1
  ``seac`` accented-composite path.

Those two fixtures exercise only straight-line outlines (boxes) and the
``seac`` composite. This file targets the remaining Type 1 charstring
mechanics on a *curved* glyph:

* **``rrcurveto`` beziers** at the extrema of a round counter (a curved ``O``
  built from four beziers, and a curved ``o``);
* **flex** — the Adobe Type 1 spec §8.3 flex mechanism: the charstring issues
  ``1 callsubr`` (Subr 1 = ``0 1 callothersubr`` → *begin flex*), then seven
  ``rmoveto`` points each followed by ``2 callsubr`` (Subr 2 = ``0 2
  callothersubr`` → *collect flex point*), then ``<flexheight> <x> <y> 0
  callsubr`` (Subr 0 = ``3 0 callothersubr pop pop setcurrentpoint`` → *end
  flex*, which collapses the seven collected ``rmoveto`` points into **two**
  ``rrcurveto`` segments approximating a near-flat curve);
* **``div``** — the flex height is fed as a rational (``100 2 div`` → 50),
  exercising the Type 1 ``div`` operator;
* **``callsubr`` / ``return``** — the standard OtherSubrs are reached through
  the four local ``/Private /Subrs`` (the real-``.pfb`` idiom, not inline
  ``callothersubr``).

The bug this surfaced and FIXED (wave 1444), in
``pypdfbox/fontbox/cff/type1_char_string.py``: the *in-memory*
``Type1Font.create_with_pfb`` path builds each ``Type1CharString`` from raw
charstring bytes / a program list but never attached the parent font's
``/Private /Subrs`` to the underlying fontTools ``T1CharString``. So
``op_callsubr`` did ``self.subrs[index]`` with ``self.subrs is None`` and
raised ``TypeError`` — the swallowed error dropped the **entire** glyph and any
flex / hint-replacement Type 1 glyph (every real ``.pfb`` ``o``/``e``/``s`` …)
decoded to a **blank** path through that path. (The embedded ``/FontFile``
reload path — the one this render oracle drives — was already correct because
fontTools' ``t1Lib`` parse attaches decompiled subrs.) The fix wires the
parent's subrs (wrapping raw bytes → ``T1CharString``) onto the charstring so
both load paths resolve ``callsubr`` identically; ``test_curved_flex_glyph_*``
below assert the previously-blank in-memory path now decodes the flex glyph and
that both paths agree byte-for-byte.

No bundled Type 1 program has curved/flex glyphs (``DemoType1.pfb`` is A/B/C
boxes; ``SeacType1.pfb`` is boxes + a seac), so the fixture
``CurvedFlexType1.pfb`` is built (via fontTools' ``t1Lib`` writer so it parses
through *both* load paths): a curved ``O`` (four ``rrcurveto`` beziers, no
flex) and a curved ``o`` whose counter uses a real ``callsubr``-driven flex on
its near-flat bottom plus a ``div``. ``test_fixture_glyph_uses_curves_and_flex``
proves the fixture really exercises the curve + flex + div path.

Each fixture is rendered through Apache PDFBox (``oracle/probes/RenderProbe``)
and through pypdfbox at 72 DPI and compared with the same fingerprint the
page-render oracle uses:

* **exact page dimensions** — a mismatch is a real bug (wrong scale rounding),
  never anti-aliasing;
* **16x16 luminance grid** — average Rec.601 luminance per cell, compared by
  mean-absolute cell diff (MAD) and worst single-cell diff (MAXDIFF). Survives
  AA / sub-pixel coverage differences (Java2D vs Pillow/aggdraw) but catches a
  blank glyph, a wrong-scale glyph, a kinked flex curve, or a wrong outline.

Gate is wave 1408's calibrated ``MAD < 6`` / ``MAXDIFF < 60``. Measured against
PDFBox 3.0.7 both sizes land at MAD ~0.2-0.3 / MAXDIFF ~6-8 (the curved + flex
glyphs paint pixel-for-pixel where PDFBox does). A *blank* render measures MAD
well outside the gate (asserted below): if the flex curve were kinked, the
``div`` wrong, or the whole glyph dropped, pypdfbox's render would diverge far
from PDFBox's, so the gate genuinely discriminates a correct curved/flex render
from a broken one.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fontTools.t1Lib import T1Font
from PIL import Image

from pypdfbox.cos import COSName, COSStream
from pypdfbox.fontbox.type1.type1_font import Type1Font
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font
from pypdfbox.pdmodel.pd_resources import PDResources
from pypdfbox.rendering import PDFRenderer
from tests.oracle.harness import requires_oracle, run_probe_text

_GRID = 16
# Same gate wave 1408 calibrated for whole-page / glyph render parity.
_MAD_TOLERANCE = 6.0
_MAXDIFF_TOLERANCE = 60

_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "fontbox" / "type1"
_PFB = _FIXTURES / "CurvedFlexType1.pfb"

# The fixture maps 'O' -> curved O (StandardEncoding 79) and 'o' -> curved flex
# o (111); StandardEncoding resolves both. Two scales exercise the glyph-space
# -> user-space divisor, and a row of glyphs fills enough of the page that the
# coarse 16x16 grid clearly separates a real curved/flex render from a blank
# one (the blank guard below relies on this).
#   (page width, page height, font size, text)
_CASES = {
    "size40": (150.0, 18.0, 40, b"OoOoOo"),
    "size60": (190.0, 24.0, 60, b"OoOo"),
}


def _build(
    out: Path, page_w: float, page_h: float, font_size: int, text: bytes
) -> Path:
    """Embed ``CurvedFlexType1.pfb`` via pypdfbox, write an explicit
    ``StandardEncoding`` (maps 79/111 -> O/o), and show ``text`` at
    ``font_size`` on a tight page."""
    pfb = _PFB.read_bytes()
    doc = PDDocument()
    try:
        while doc.get_number_of_pages() > 0:
            doc.remove_page(0)
        page = PDPage(PDRectangle(0.0, 0.0, page_w, page_h))
        doc.add_page(page)

        font = PDType1Font.load(doc, pfb)
        # Without an explicit /Encoding the renderer cannot resolve code ->
        # glyph name for an embedded Type 1 (cross-module gap documented in
        # test_type1_glyph_render_oracle.py); StandardEncoding maps 79/111 ->
        # O/o, matching the program's own built-in encoding.
        font._dict.set_item(  # noqa: SLF001
            COSName.get_pdf_name("Encoding"),
            COSName.get_pdf_name("StandardEncoding"),
        )

        res = PDResources()
        res.put(COSName.get_pdf_name("F1"), font)
        page.set_resources(res)

        cs = COSStream()
        cs.set_data(b"BT\n/F1 %d Tf\n4 3 Td\n(%s) Tj\nET\n" % (font_size, text))
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


# ---------------------------------------------------------------------------
# fixture proof: the test glyph really uses curves + flex + div
# ---------------------------------------------------------------------------


def test_fixture_glyph_uses_curves_and_flex() -> None:
    """Prove the test exercises the curve + flex + div path: the fixture's
    ``o`` charstring uses ``rrcurveto`` (real beziers), reaches the flex
    machinery through ``callsubr`` (into the standard OtherSubrs wrapper
    subroutines), and feeds the flex height via ``div``. If the fixture ever
    changed so ``o`` were a straight-line / non-flex outline, the render test
    below would no longer cover the flex path."""
    font = T1Font(str(_PFB))
    font.parse()
    charstrings = font.font["CharStrings"]
    cs = charstrings["o"]
    cs.decompile()
    program = cs.program
    assert "rrcurveto" in program, (
        f"o has no rrcurveto (program={program}); the curve path is not "
        f"exercised"
    )
    assert "callsubr" in program, (
        f"o has no callsubr (program={program}); the flex / OtherSubrs path "
        f"is not exercised"
    )
    assert "div" in program, (
        f"o has no div (program={program}); the div operator is not exercised"
    )
    # The standard OtherSubrs wrapper subroutines must be present (Subr 1 =
    # begin flex, Subr 2 = flex point, Subr 0 = end flex), each fronting a
    # callothersubr.
    subrs = font.font["Private"]["Subrs"]
    assert len(subrs) >= 3, f"expected >=3 standard subrs, got {len(subrs)}"
    for idx in (0, 1, 2):
        subrs[idx].decompile()
        assert "callothersubr" in subrs[idx].program, (
            f"Subr {idx} does not front a callothersubr "
            f"(program={subrs[idx].program}); the OtherSubrs flex machinery "
            f"is not exercised"
        )
    # The curved 'O' is plain beziers (no flex) — confirms the simple-curve
    # case is distinct from the flex case.
    o_caps = charstrings["O"]
    o_caps.decompile()
    assert "rrcurveto" in o_caps.program
    assert "callsubr" not in o_caps.program


def test_curved_flex_glyph_decodes_via_in_memory_pfb_path() -> None:
    """Regression guard for the wave-1444 fix: the in-memory
    ``create_with_pfb`` path must decode the flex ``o`` to a real curved
    outline (it previously dropped to a blank path because the parent font's
    ``/Private /Subrs`` were not attached to the charstring, so ``callsubr``
    raised and the whole glyph was swallowed)."""
    pfb = _PFB.read_bytes()
    font = Type1Font.create_with_pfb(pfb)
    path = font.get_path("o")
    tags = [cmd[0] for cmd in path]
    assert path, "flex glyph 'o' decoded to a blank path via create_with_pfb"
    # The flex collapses 7 collected points into 2 rrcurveto segments; with
    # the 4 explicit beziers that is 6 curveto commands total.
    assert tags.count("curveto") == 6, (
        f"flex 'o' produced {tags.count('curveto')} curves, expected 6 "
        f"(4 explicit + 2 flex-generated); tags={tags}"
    )
    assert font.get_width("o") == 600.0


def test_curved_flex_glyph_both_load_paths_agree() -> None:
    """Both Type 1 load paths must produce the *same* outline for the flex
    ``o``: the embedded ``/FontFile`` reload path (``from_bytes``, subrs
    attached by fontTools) and the in-memory ``create_with_pfb`` path (subrs
    attached by the wave-1444 fix). A divergence would mean one path's flex /
    callsubr handling is wrong."""
    pfb = _PFB.read_bytes()
    in_memory = Type1Font.create_with_pfb(pfb).get_path("o")
    doc = PDDocument()
    try:
        program = PDType1Font.load(doc, pfb)._get_type1_font()  # noqa: SLF001
        assert program is not None
        reload_path = program.get_path("o")
    finally:
        doc.close()
    assert in_memory == reload_path, (
        "in-memory and reload load paths disagree on the flex 'o' outline"
    )


# ---------------------------------------------------------------------------
# differential tests
# ---------------------------------------------------------------------------


@requires_oracle
@pytest.mark.parametrize("label", list(_CASES), ids=list(_CASES))
def test_type1_flex_render_matches_pdfbox(label: str, tmp_path: Path) -> None:
    fixture = _build(tmp_path / f"{label}.pdf", *_CASES[label])
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

    # (b) Perceptual grid parity within tolerance — catches a blank glyph, a
    #     wrong-scale glyph, a kinked flex curve, or a wrong outline.
    diffs = [abs(a - b) for a, b in zip(java_grid, py_grid, strict=True)]
    mad = sum(diffs) / len(diffs)
    maxdiff = max(diffs)
    assert mad < _MAD_TOLERANCE, (
        f"{label}: mean abs cell diff {mad:.2f} >= {_MAD_TOLERANCE} "
        f"(maxdiff={maxdiff}) — curved/flex Type 1 glyph render grossly "
        f"divergent, not AA"
    )
    assert maxdiff < _MAXDIFF_TOLERANCE, (
        f"{label}: worst cell diff {maxdiff} >= {_MAXDIFF_TOLERANCE} "
        f"(mad={mad:.2f}) — a region diverges far beyond anti-aliasing"
    )


@requires_oracle
@pytest.mark.parametrize("label", list(_CASES), ids=list(_CASES))
def test_blank_page_far_from_flex_reference(label: str, tmp_path: Path) -> None:
    """Guard the gate: a blank-white page is far outside tolerance versus
    PDFBox's actual (curved/flex-glyph-bearing) render. Proves the curved +
    flex glyphs really paint — if the flex curve were dropped (the wave-1444
    bug on the in-memory path) or kinked, pypdfbox's own render would be
    blank/wrong and a too-loose gate could (wrongly) pass; this asserts a
    blank page does NOT pass, so the gate genuinely discriminates a correct
    curved/flex render from a broken one."""
    fixture = _build(tmp_path / f"{label}.pdf", *_CASES[label])
    _dims, java_grid = _oracle_signature(fixture)
    blank = [255] * (_GRID * _GRID)
    diffs = [abs(a - b) for a, b in zip(java_grid, blank, strict=True)]
    mad = sum(diffs) / len(diffs)
    assert mad >= _MAD_TOLERANCE, (
        f"{label}: tolerance too loose — a blank page passes the MAD gate, so "
        f"a dropped curved/flex Type 1 glyph would not be caught (blank MAD "
        f"{mad:.2f})"
    )
