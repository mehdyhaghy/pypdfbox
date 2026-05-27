"""Live PDFBox differential parity for content-stream operator robustness.

Exercises the renderer + text-extractor's *operator-dispatch tolerance* —
the path that must silently survive malformed / unknown operators while
still painting and extracting all the *valid* content around them. PDF spec
§7.8.2 (``BX``/``EX`` compatibility operators) plus PDFBox's lenient
``unsupportedOperator`` / ``operatorException`` handling are the upstream
reference; we compare against Apache PDFBox 3.0.7 on identical PDFs.

Each PDF draws two solid square glyphs (``A`` then ``B``) from an embedded
square-glyph TrueType font so both renderers paint the *identical* outline
(this isolates the operator-robustness path from font-substitution shape
differences) and so the extracted text is deterministic. A malformed /
unknown operator is injected between, before, or after the valid drawing
ops; a correct engine must ignore the bad operator and still render +
extract both glyphs.

Cases (all built in-process, 300x200pt page):

(a) ``bx_ex``           — ``BX /Foo somemadeup EX`` wraps an unknown
    operator + stray operand between the two glyph draws. PDF §7.8.2: an
    unrecognised operator *inside* a ``BX``/``EX`` compatibility section
    must be silently ignored. Both glyphs must still paint/extract.
(b) ``unknown_outside`` — a bare ``somemadeup`` unknown operator *outside*
    any ``BX``/``EX`` section, between the glyph draws. PDFBox logs + skips
    it (``unsupportedOperator``); the valid content is unaffected.
(c) ``extra_operands``  — extra numeric operands left on the stack before
    ``Td`` (``1 2 3 30 60 Td``). The operator consumes its trailing
    operands; the leading surplus is discarded, not an error.
(d) ``truncated``       — a garbled / truncated operator token at
    end-of-stream (``...SomeTrunc`` with no terminator). The parser must
    tokenise the valid content first and tolerate the trailing garbage.

Render parity: the coarse 16x16 average-luminance fingerprint emitted by
``oracle/probes/RenderProbe.java`` (mirrors ``test_render_oracle.py``);
gate at ``MAD < 6.0`` / ``MAXDIFF < 60`` — above the AA ceiling, well below
a dropped-glyph floor. Text parity: byte-exact against
``oracle/probes/TextExtractProbe.java``.

A guard test confirms the gate discriminates: a *blank* page (what a crash
or dropped-content engine would effectively produce) scores far over the
render gate against PDFBox's two-glyph reference.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from PIL import Image

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName, COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.font.pd_font_descriptor import PDFontDescriptor
from pypdfbox.pdmodel.font.pd_true_type_font import PDTrueTypeFont
from pypdfbox.rendering import PDFRenderer
from pypdfbox.text import PDFTextStripper
from tests.oracle.harness import requires_oracle, run_probe_text

_GRID = 16
_MAD_TOLERANCE = 6.0
_MAXDIFF_TOLERANCE = 60
_PAGE_W = 300.0
_PAGE_H = 200.0


# --------------------------------------------------------------------------
# fingerprint helpers (must match RenderProbe.java's cell mapping exactly)
# --------------------------------------------------------------------------


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
        round(total[i] / count[i]) if count[i] else 255 for i in range(_GRID * _GRID)
    ]


def _render_signature(pdf: Path) -> tuple[tuple[int, int], list[int]]:
    lines = run_probe_text("RenderProbe", str(pdf), "0").splitlines()
    width, height = (int(v) for v in lines[0].split())
    grid = [int(v) for v in lines[1].split()]
    assert len(grid) == _GRID * _GRID
    return (width, height), grid


def _diff(a: list[int], b: list[int]) -> tuple[float, int]:
    diffs = [abs(x - y) for x, y in zip(a, b, strict=True)]
    return sum(diffs) / len(diffs), max(diffs)


# --------------------------------------------------------------------------
# PDF builders
# --------------------------------------------------------------------------


def _square_ttf_bytes() -> bytes:
    """A TrueType font whose ``A`` / ``B`` glyphs are solid 800x800-em
    squares, so the painted outline is identical in both renderers and the
    extracted text is deterministic."""
    from fontTools.fontBuilder import FontBuilder
    from fontTools.pens.ttGlyphPen import TTGlyphPen

    fb = FontBuilder(1024, isTTF=True)
    fb.setupGlyphOrder([".notdef", "A", "B"])
    fb.setupCharacterMap({0x41: "A", 0x42: "B"})

    def sq() -> object:
        pen = TTGlyphPen(None)
        pen.moveTo((100, 100))
        pen.lineTo((900, 100))
        pen.lineTo((900, 900))
        pen.lineTo((100, 900))
        pen.closePath()
        return pen.glyph()

    fb.setupGlyf({".notdef": TTGlyphPen(None).glyph(), "A": sq(), "B": sq()})
    fb.setupHorizontalMetrics({".notdef": (0, 0), "A": (1024, 0), "B": (1024, 0)})
    fb.setupHorizontalHeader(ascent=900, descent=-100)
    fb.setupNameTable({"familyName": "DejaVuSquare", "styleName": "Regular"})
    fb.setupOS2(sTypoAscender=900, usWinAscent=900, usWinDescent=100)
    fb.setupPost()
    buf = io.BytesIO()
    fb.save(buf)
    return buf.getvalue()


def _make_doc() -> tuple[PDDocument, PDPage]:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, _PAGE_W, _PAGE_H))
    doc.add_page(page)
    return doc, page


def _add_square_font(page: PDPage) -> str:
    """Embed the square-glyph TTF on ``page`` and return its resource name."""
    font_file2 = COSStream()
    font_file2.set_raw_data(_square_ttf_bytes())
    descriptor = PDFontDescriptor(COSDictionary())
    descriptor.set_font_file2(font_file2)
    font_dict = COSDictionary()
    font_dict.set_item(COSName.TYPE, COSName.get_pdf_name("Font"))
    font_dict.set_item(COSName.SUBTYPE, COSName.get_pdf_name("TrueType"))
    font_dict.set_item(
        COSName.get_pdf_name("BaseFont"), COSName.get_pdf_name("DejaVuSquare")
    )
    font_dict.set_item(
        COSName.get_pdf_name("FontDescriptor"), descriptor.get_cos_object()
    )
    font_dict.set_item(COSName.get_pdf_name("FirstChar"), COSInteger.get(65))
    font_dict.set_item(COSName.get_pdf_name("LastChar"), COSInteger.get(66))
    widths = COSArray()
    widths.add(COSInteger.get(1000))
    widths.add(COSInteger.get(1000))
    font_dict.set_item(COSName.get_pdf_name("Widths"), widths)
    font = PDTrueTypeFont(font_dict)
    resources = page.get_resources()
    fname = resources.add(font)
    page.set_resources(resources)
    return fname.get_name()


def _save(doc: PDDocument, page: PDPage, ops: bytes, path: Path) -> None:
    cs = COSStream()
    cs.set_raw_data(ops)
    page.get_cos_object().set_item(COSName.CONTENTS, cs)
    try:
        doc.save(str(path))
    finally:
        doc.close()


# The valid scaffold (used by every builder): draw glyph ``A`` at the left,
# glyph ``B`` at the right. The bad operator is injected in the gap.
def _build_bx_ex(path: Path) -> None:
    doc, page = _make_doc()
    fn = _add_square_font(page).encode("ascii")
    ops = (
        b"q\nBT\n/" + fn + b" 40 Tf\n"
        b"30 150 Td\n(A) Tj\n"
        # PDF spec §7.8.2: unknown operator (+ stray operand) inside a
        # BX/EX compatibility section must be silently ignored.
        b"BX /Foo somemadeup EX\n"
        b"0 -60 Td\n(B) Tj\n"
        b"ET\nQ\n"
    )
    _save(doc, page, ops, path)


def _build_unknown_outside(path: Path) -> None:
    doc, page = _make_doc()
    fn = _add_square_font(page).encode("ascii")
    ops = (
        b"q\nBT\n/" + fn + b" 40 Tf\n"
        b"30 150 Td\n(A) Tj\n"
        # Bare unknown operator OUTSIDE any BX/EX — PDFBox logs + skips it.
        b"somemadeup\n"
        b"0 -60 Td\n(B) Tj\n"
        b"ET\nQ\n"
    )
    _save(doc, page, ops, path)


def _build_extra_operands(path: Path) -> None:
    doc, page = _make_doc()
    fn = _add_square_font(page).encode("ascii")
    ops = (
        b"q\nBT\n/" + fn + b" 40 Tf\n"
        # Surplus operands before Td (consumes only the trailing 2).
        b"1 2 3 30 150 Td\n(A) Tj\n"
        b"9 9 0 -60 Td\n(B) Tj\n"
        b"ET\nQ\n"
    )
    _save(doc, page, ops, path)


def _build_truncated(path: Path) -> None:
    doc, page = _make_doc()
    fn = _add_square_font(page).encode("ascii")
    ops = (
        b"q\nBT\n/" + fn + b" 40 Tf\n"
        b"30 150 Td\n(A) Tj\n"
        b"0 -60 Td\n(B) Tj\n"
        b"ET\nQ\n"
        # Garbled / truncated operator token at end-of-stream, no
        # terminator. Parser must tokenise the valid content first.
        b"50 50 m\n150 150 l\nSomeTruncatedOperator"
    )
    _save(doc, page, ops, path)


def _build_blank(path: Path) -> None:
    """Guard fixture: a page that draws nothing — what a crashing or
    content-dropping engine would effectively produce."""
    doc, page = _make_doc()
    _add_square_font(page)
    _save(doc, page, b"q\nQ\n", path)


_BUILDERS = {
    "bx_ex": _build_bx_ex,
    "unknown_outside": _build_unknown_outside,
    "extra_operands": _build_extra_operands,
    "truncated": _build_truncated,
}


def _render_py(pdf: Path) -> Image.Image:
    with PDDocument.load(pdf) as doc:
        return PDFRenderer(doc).render_image_with_dpi(0, 72.0)


def _extract_py(pdf: Path) -> str:
    with PDDocument.load(pdf) as doc:
        return PDFTextStripper().get_text(doc)


# --------------------------------------------------------------------------
# differential tests
# --------------------------------------------------------------------------


@requires_oracle
@pytest.mark.parametrize("label", list(_BUILDERS), ids=list(_BUILDERS))
def test_render_tolerates_bad_operator_like_pdfbox(
    label: str, tmp_path: Path
) -> None:
    """The page renders identically to PDFBox: both valid glyphs paint and
    the bad operator is tolerated (no crash, no lost content)."""
    pdf = tmp_path / f"{label}.pdf"
    _BUILDERS[label](pdf)

    (java_w, java_h), java_grid = _render_signature(pdf)
    img = _render_py(pdf)
    py_w, py_h = img.size
    py_grid = _grid_from_image(img)

    assert (py_w, py_h) == (java_w, java_h), (
        f"{label}: rendered dimensions diverge from PDFBox: "
        f"pypdfbox={py_w}x{py_h} java={java_w}x{java_h}"
    )

    mad, maxdiff = _diff(java_grid, py_grid)
    assert mad < _MAD_TOLERANCE, (
        f"{label}: mean abs cell diff {mad:.2f} >= {_MAD_TOLERANCE} "
        f"(maxdiff={maxdiff}) — bad operator dropped valid content / diverged"
    )
    assert maxdiff < _MAXDIFF_TOLERANCE, (
        f"{label}: worst cell diff {maxdiff} >= {_MAXDIFF_TOLERANCE} "
        f"(mad={mad:.2f}) — a region diverges far beyond anti-aliasing"
    )


@requires_oracle
@pytest.mark.parametrize("label", list(_BUILDERS), ids=list(_BUILDERS))
def test_extract_tolerates_bad_operator_like_pdfbox(
    label: str, tmp_path: Path
) -> None:
    """The text extracts byte-identically to PDFBox: the valid glyphs are
    recovered around the bad operator."""
    pdf = tmp_path / f"{label}.pdf"
    _BUILDERS[label](pdf)

    java_text = run_probe_text("TextExtractProbe", str(pdf))
    py_text = _extract_py(pdf)
    assert py_text == java_text, (
        f"{label}: extracted text diverges from PDFBox: "
        f"pypdfbox={py_text!r} java={java_text!r}"
    )
    # Both valid glyphs must survive the bad operator.
    assert "A" in py_text and "B" in py_text, (
        f"{label}: a valid glyph was lost: {py_text!r}"
    )


@requires_oracle
def test_blank_render_would_fail_robustness_gate(tmp_path: Path) -> None:
    """Guard the threshold: a *blank* page (what a crashing or
    content-dropping engine effectively produces) scores far over the
    render gate against PDFBox's two-glyph ``bx_ex`` reference. Confirms
    the gate discriminates tolerated-bad-operator renders from
    lost-content failures rather than passing everything."""
    good = tmp_path / "bx_ex.pdf"
    blank = tmp_path / "blank.pdf"
    _build_bx_ex(good)
    _build_blank(blank)

    _dims, java_good_grid = _render_signature(good)
    py_blank_grid = _grid_from_image(_render_py(blank))
    mad, maxdiff = _diff(java_good_grid, py_blank_grid)
    assert mad >= _MAD_TOLERANCE and maxdiff >= _MAXDIFF_TOLERANCE, (
        f"robustness gate too loose: a blank (content-dropped) render "
        f"passes (MAD={mad:.2f}, MAXDIFF={maxdiff})"
    )
