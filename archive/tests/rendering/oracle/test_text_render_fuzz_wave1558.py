"""Live PDFBox differential FUZZ of the PageDrawer TEXT rendering surface
(PDF 32000-1 §9.3.6 / Table 106 text rendering modes, §9.4.4 text-rendering
matrix application, §9.6.5 Type 3 charproc glyphs).

Where ``test_text_render_mode_oracle.py`` pins a 16x16 *luminance grid* on
``Tr`` 0/1/2/3/7 with an embedded Type 1 outline font, this wave *fuzzes the
edges that test does not reach*:

* the clip-accumulating modes ``Tr`` 4 / 5 / 6 (fill / stroke / fill+stroke
  that ALSO add the glyph outline to the clip at ``ET``);
* ``Tr`` 7 standalone (clip-only, no following fill — the page must be blank);
* a ``Tr`` 7 clip followed by a page fill (text-shaped clip — only glyph
  interiors survive);
* text under a scaled text matrix and under a rotated text matrix
  (``Tm``-driven text-rendering-matrix application);
* a heavy stroke width under a stroke mode;
* a zero-size font (``0 Tf`` — nothing visible should paint);
* a Type 3 charproc glyph;
* **the no-embedded-outline (placeholder-box) path under modes 0 / 3 / 7** —
  a Standard-14-style font with no glyph program we can rasterise. pypdfbox
  draws a faint placeholder box for such glyphs; that box MUST still honour
  the no-paint modes (3 invisible, 7 clip-only).

Pixel-exact parity is impossible (Java2D vs skia/aggdraw AA — see
``CHANGES.md`` / ``test_render_oracle.py``), and PDFBox renders Standard-14
fonts with its bundled real outlines whereas pypdfbox falls back to a
placeholder box, so this surface compares only **gross painted-region facts**
projected by ``oracle/probes/TextRenderFuzzProbe.java``:

* exact rendered pixel dimensions (a mismatch is a real bug, not AA);
* the painted *emptiness verdict* — the real-bug signal: text that should
  paint must be non-empty on both sides; text that must NOT paint (mode 3,
  mode 7 with no fill, zero-size font) must be empty on both sides.

For the *outline* cases (embedded Type 1 + Type 3) the painted bounding box is
additionally compared within a generous slop, since both renderers paint the
real glyph shapes in roughly the same place. The placeholder-font cases compare
emptiness only (pypdfbox boxes vs PDFBox outlines are coarsely different shapes).

The real bug this fuzz caught (wave 1558): the no-embedded-outline placeholder
box was drawn regardless of the text rendering mode, so a font with no glyph
program rendered an identical *visible* box under fill, invisible (mode 3) and
clip-only (mode 7) — i.e. invisible text leaked visible marks. Fixed in
``pypdfbox/rendering/pdf_renderer.py`` (``_draw_glyph`` now suppresses the
placeholder for the no-paint modes 3 and 7); the ``placeholder_*`` cases below
pin the corrected behaviour.

Fixtures are tiny one-page PDFs synthesised in-memory (the embedded Type 1 uses
the committed ``DemoType1.pfb``; the Type 3 font is built from raw charprocs;
the placeholder font is a bare ``PDType1Font``). No new committed binaries.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSStream,
)
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font
from pypdfbox.pdmodel.font.pd_type3_font import PDType3Font
from pypdfbox.pdmodel.pd_resources import PDResources
from pypdfbox.rendering import PDFRenderer
from tests.oracle.harness import requires_oracle, run_probe_text

_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "fontbox" / "type1"

_PW, _PH = 160.0, 60.0  # page px == user units at 72 DPI
_FS = 36  # font size for the outline cases
_WHITE_THRESHOLD = 250  # luma < this counts as painted (matches the probe)
_BBOX_SLOP = 4  # px tolerance on the painted bbox edges (AA + outline drift)

_TEXT = b"ABCAB"
_FONT_MATRIX = [0.001, 0.0, 0.0, 0.001, 0.0, 0.0]


# ---------------------------------------------------------------------------
# font kinds — each maps a label to a builder that returns a finished PDF.
# ---------------------------------------------------------------------------


def _embedded_type1_doc(content: bytes, out: Path) -> Path:
    """One-page PDF whose /F1 is the embedded ``DemoType1.pfb`` (real Type 1
    outlines, so the genuine outline draw path runs — not the placeholder)."""
    pfb = (_FIXTURES / "DemoType1.pfb").read_bytes()
    doc = PDDocument()
    try:
        while doc.get_number_of_pages() > 0:
            doc.remove_page(0)
        page = PDPage(PDRectangle(0.0, 0.0, _PW, _PH))
        doc.add_page(page)
        font = PDType1Font.load(doc, pfb)
        font._dict.set_item(  # noqa: SLF001
            COSName.get_pdf_name("Encoding"),
            COSName.get_pdf_name("StandardEncoding"),
        )
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


def _placeholder_doc(content: bytes, out: Path) -> Path:
    """One-page PDF whose /F1 is a bare ``PDType1Font`` (no embedded program) —
    a Standard-14-style reference for which pypdfbox draws a placeholder box.
    Apache PDFBox renders its bundled outlines; we compare emptiness only."""
    doc = PDDocument()
    try:
        while doc.get_number_of_pages() > 0:
            doc.remove_page(0)
        page = PDPage(PDRectangle(0.0, 0.0, _PW, _PH))
        font_dict = COSDictionary()
        font_dict.set_item(COSName.TYPE, COSName.get_pdf_name("Font"))
        font_dict.set_item(
            COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Type1")
        )
        font_dict.set_item(
            COSName.get_pdf_name("BaseFont"), COSName.get_pdf_name("Helvetica")
        )
        font = PDType1Font(font_dict)
        res = PDResources()
        res.put(COSName.get_pdf_name("F1"), font)
        page.set_resources(res)
        doc.add_page(page)
        cs = COSStream()
        cs.set_data(content)
        page.set_contents(cs)
        doc.save(str(out))
    finally:
        doc.close()
    return out


def _char_proc_box() -> COSStream:
    """Code 65 ('box'): a ``d1`` coloured-form glyph — a filled 750x750 box that
    inherits the text-state non-stroking colour."""
    stream = COSStream()
    stream.set_data(b"750 0 0 0 750 750 d1\n0 0 750 750 re f\n")
    return stream


def _type3_doc(content: bytes, out: Path) -> Path:
    """One-page PDF whose /F1 is a Type 3 font with a single filled-box glyph."""
    char_procs = COSDictionary()
    char_procs.set_item(COSName.get_pdf_name("box"), _char_proc_box())
    differences = COSArray()
    differences.add(COSInteger.get(65))
    differences.add(COSName.get_pdf_name("box"))
    enc = COSDictionary()
    enc.set_item(COSName.TYPE, COSName.get_pdf_name("Encoding"))
    enc.set_item(COSName.get_pdf_name("Differences"), differences)

    font_dict = COSDictionary()
    font_dict.set_item(COSName.TYPE, COSName.get_pdf_name("Font"))
    font_dict.set_item(
        COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Type3")
    )
    font_dict.set_item(COSName.get_pdf_name("Name"), COSName.get_pdf_name("T3"))
    font_dict.set_item(
        COSName.get_pdf_name("FontMatrix"),
        COSArray([COSFloat(v) for v in _FONT_MATRIX]),
    )
    font_dict.set_item(
        COSName.get_pdf_name("FontBBox"),
        COSArray([COSInteger.get(v) for v in (0, 0, 750, 750)]),
    )
    font_dict.set_item(COSName.get_pdf_name("CharProcs"), char_procs)
    font_dict.set_item(COSName.get_pdf_name("Encoding"), enc)
    font_dict.set_int(COSName.FIRST_CHAR, 65)
    font_dict.set_int(COSName.LAST_CHAR, 65)
    font_dict.set_item(
        COSName.get_pdf_name("Widths"), COSArray([COSFloat(750.0)])
    )

    doc = PDDocument()
    try:
        while doc.get_number_of_pages() > 0:
            doc.remove_page(0)
        page = PDPage(PDRectangle(0.0, 0.0, _PW, _PH))
        doc.add_page(page)
        font = PDType3Font(font_dict)
        font.set_resources(PDResources())
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
# fuzz cases. ``builder`` selects the font kind; ``content`` is the page stream.
# ``expect_painted`` is the PDFBox-3.0.7 emptiness verdict; ``check_bbox`` marks
# outline cases whose painted bbox should also roughly coincide with PDFBox.
# ---------------------------------------------------------------------------


class _Case:
    __slots__ = ("builder", "content", "expect_painted", "check_bbox")

    def __init__(self, builder, content, expect_painted, check_bbox):
        self.builder = builder
        self.content = content
        self.expect_painted = expect_painted
        self.check_bbox = check_bbox


def _bt(mode: int, *, fill=b"0 0 0 rg", stroke=b"", lw=b"") -> bytes:
    """Build a simple BT..ET that shows ``_TEXT`` under ``mode`` at _FS."""
    return (
        b"BT\n/F1 %d Tf\n%s\n%s%s\n4 12 Td\n%d Tr\n(%s) Tj\nET\n"
        % (_FS, fill, stroke, lw, mode, _TEXT)
    )


_CASES: dict[str, _Case] = {
    # --- clip-accumulating modes 4/5/6 on the embedded outline font ---
    # No following fill, so only the painted glyph marks themselves show.
    "tr4_fill_clip": _Case(
        _embedded_type1_doc, _bt(4, fill=b"1 0 0 rg"), True, True
    ),
    "tr5_stroke_clip": _Case(
        _embedded_type1_doc, _bt(5, stroke=b"0 0 1 RG", lw=b"1 w"), True, True
    ),
    "tr6_fill_stroke_clip": _Case(
        _embedded_type1_doc,
        _bt(6, fill=b"1 0 0 rg", stroke=b"0 0 1 RG", lw=b"1 w"),
        True,
        True,
    ),
    # --- mode 7 standalone: clip-only, NO following paint => blank page ---
    "tr7_clip_only_blank": _Case(_embedded_type1_doc, _bt(7), False, False),
    # --- mode 7 + page fill: text-shaped clip, only glyph interiors paint ---
    "tr7_clip_then_fill": _Case(
        _embedded_type1_doc,
        b"q\nBT\n/F1 %d Tf\n4 12 Td\n7 Tr\n(%s) Tj\nET\n"
        b"1 0 0 rg\n0 0 %d %d re\nf\nQ\n" % (_FS, _TEXT, int(_PW), int(_PH)),
        True,
        True,
    ),
    # --- text-rendering-matrix: scaled text matrix (Tm 2x) ---
    "tm_scaled": _Case(
        _embedded_type1_doc,
        b"BT\n/F1 18 Tf\n0 0 0 rg\n2 0 0 2 4 12 Tm\n(%s) Tj\nET\n" % _TEXT,
        True,
        True,
    ),
    # --- text-rendering-matrix: rotated text matrix (~20deg) ---
    "tm_rotated": _Case(
        _embedded_type1_doc,
        b"BT\n/F1 %d Tf\n0 0 0 rg\n"
        b"0.94 0.34 -0.34 0.94 10 8 Tm\n(AB) Tj\nET\n" % _FS,
        True,
        True,
    ),
    # --- heavy stroke width under a stroke mode ---
    "stroke_thick": _Case(
        _embedded_type1_doc,
        _bt(1, stroke=b"0 0 0 RG", lw=b"3 w"),
        True,
        True,
    ),
    # --- zero-size font: nothing visible should paint ---
    "zero_size_font": _Case(
        _embedded_type1_doc,
        b"BT\n/F1 0 Tf\n0 0 0 rg\n4 12 Td\n0 Tr\n(%s) Tj\nET\n" % _TEXT,
        False,
        False,
    ),
    # --- Type 3 charproc glyph (filled box, inherits red text state) ---
    "type3_fill": _Case(
        _type3_doc,
        b"BT\n1 0 0 rg\n/F1 40 Tf\n4 4 Td\n<41> Tj\nET\n",
        True,
        True,
    ),
    "type3_invisible": _Case(
        _type3_doc,
        b"BT\n1 0 0 rg\n/F1 40 Tf\n4 4 Td\n3 Tr\n<41> Tj\nET\n",
        False,
        False,
    ),
    # --- no-embedded-outline placeholder path (the wave-1558 bug surface) ---
    # PDFBox paints bundled Helvetica outlines; pypdfbox draws a placeholder
    # box. Compare emptiness only: both must paint for the visible modes and
    # both must be blank for the no-paint modes.
    "placeholder_fill": _Case(_placeholder_doc, _bt(0), True, False),
    "placeholder_stroke": _Case(
        _placeholder_doc, _bt(1, stroke=b"0 0 0 RG", lw=b"1 w"), True, False
    ),
    "placeholder_invisible": _Case(_placeholder_doc, _bt(3), False, False),
    "placeholder_clip_only": _Case(_placeholder_doc, _bt(7), False, False),
}


# ---------------------------------------------------------------------------
# fingerprint helpers — mirror TextRenderFuzzProbe.java exactly
# ---------------------------------------------------------------------------


def _painted_facts(img: Image.Image) -> tuple[int, tuple[int, int, int, int]]:
    """(painted_count, (minx, miny, maxx, maxy)); empty => (0, (-1,-1,-1,-1))."""
    gray = img.convert("L")
    width, height = gray.size
    pixels = gray.load()
    painted = 0
    minx = miny = maxx = maxy = -1
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
    return painted, (minx, miny, maxx, maxy)


def _oracle_facts(
    fixture: Path,
) -> tuple[tuple[int, int], int, tuple[int, int, int, int]]:
    lines = run_probe_text("TextRenderFuzzProbe", str(fixture), "0").splitlines()
    width, height = (int(v) for v in lines[0].split())
    vals = [int(v) for v in lines[1].split()]
    return (width, height), vals[0], (vals[1], vals[2], vals[3], vals[4])


def _py_facts(
    fixture: Path,
) -> tuple[tuple[int, int], int, tuple[int, int, int, int]]:
    with PDDocument.load(fixture) as doc:
        img = PDFRenderer(doc).render_image_with_dpi(0, 72.0)
    painted, bbox = _painted_facts(img)
    return img.size, painted, bbox


# ---------------------------------------------------------------------------
# differential tests
# ---------------------------------------------------------------------------


@requires_oracle
@pytest.mark.parametrize("label", list(_CASES), ids=list(_CASES))
def test_text_render_fuzz_matches_pdfbox(label: str, tmp_path: Path) -> None:
    """Each fuzz case must match Apache PDFBox's gross painted-region facts:
    identical dimensions and the same emptiness verdict. Outline cases also
    compare the painted bbox within ``_BBOX_SLOP``. Placeholder-font cases
    compare emptiness only (PDFBox paints real outlines, pypdfbox a box)."""
    case = _CASES[label]
    fixture = case.builder(case.content, tmp_path / f"{label}.pdf")

    (java_w, java_h), java_painted, java_bbox = _oracle_facts(fixture)
    (py_w, py_h), py_painted, py_bbox = _py_facts(fixture)

    # (a) Exact pixel dimensions — a mismatch is a real bug, not AA.
    assert (py_w, py_h) == (java_w, java_h), (
        f"{label}: rendered dims diverge py={py_w}x{py_h} java={java_w}x{java_h}"
    )

    # (b) Emptiness verdict must agree — the real-bug signal. Text PDFBox
    #     paints must not be blank on our side, and text that must NOT paint
    #     (mode 3, mode 7 without a fill, zero-size font) must stay blank.
    java_empty = java_painted == 0
    py_empty = py_painted == 0
    assert py_empty == java_empty, (
        f"{label}: painted-emptiness diverges — pypdfbox {py_painted}px, "
        f"java {java_painted}px. Text one renderer paints the other leaves "
        f"blank (or invisible text painting) is a real text-render bug, not AA."
    )

    if java_empty or not case.check_bbox:
        return

    # (c) Painted bbox within slop for the outline cases (AA + outline drift).
    for axis, (p, j) in enumerate(zip(py_bbox, java_bbox, strict=True)):
        assert abs(p - j) <= _BBOX_SLOP, (
            f"{label}: painted bbox axis {axis} diverges py={py_bbox} "
            f"java={java_bbox} (slop={_BBOX_SLOP})"
        )


@pytest.mark.parametrize("label", list(_CASES), ids=list(_CASES))
def test_text_render_fuzz_emptiness_pinned(label: str, tmp_path: Path) -> None:
    """Oracle-free pin of the documented PDFBox 3.0.7 emptiness verdict — runs
    everywhere (no Java needed) so the corrected placeholder-mode semantics
    (no-paint modes 3/7 leave the placeholder font blank) stay green in CI
    without the live jar. A flip here is a text-render regression, not AA."""
    case = _CASES[label]
    fixture = case.builder(case.content, tmp_path / f"{label}.pdf")
    _dims, painted, _bbox = _py_facts(fixture)
    assert (painted > 0) == case.expect_painted, (
        f"{label}: expected painted={case.expect_painted} but got {painted}px "
        f"(PDFBox 3.0.7 reference)."
    )


@requires_oracle
def test_invisible_placeholder_blank_like_pdfbox(tmp_path: Path) -> None:
    """Direct regression pin for the wave-1558 bug: a no-embedded-outline font
    under ``Tr`` 3 (invisible) must render BLANK, matching PDFBox — not the
    old visible placeholder box. Cross-checks that the visible mode 0 of the
    same font DOES paint, proving the suppression is mode-specific."""
    invisible = _placeholder_doc(_bt(3), tmp_path / "ph_inv.pdf")
    visible = _placeholder_doc(_bt(0), tmp_path / "ph_vis.pdf")

    (_jw, _jh), java_inv_painted, _b = _oracle_facts(invisible)
    assert java_inv_painted == 0, "oracle sanity: PDFBox renders Tr 3 blank"

    _dims, py_inv_painted, _b2 = _py_facts(invisible)
    assert py_inv_painted == 0, (
        "placeholder-mode regression: pypdfbox painted a visible box for "
        "invisible (Tr 3) text where it must paint nothing"
    )
    _dims2, py_vis_painted, _b3 = _py_facts(visible)
    assert py_vis_painted > 0, (
        "sanity: the same placeholder font must still paint under Tr 0 (fill)"
    )
