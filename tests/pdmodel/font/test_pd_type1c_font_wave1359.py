"""``PDType1CFont.get_average_character_width`` / ``get_average_font_width``.

Upstream ``PDType1CFont.getAverageFontWidth`` returns its private
``getAverageCharacterWidth``, a hard-coded ``500`` (marked "not
implemented, highly suspect"). pypdfbox used to estimate a real mean from
``/Widths``, the embedded CFF charstrings, ``defaultWidthX`` and the
Standard 14 AFM; the value feeds text extraction's space-width fallback, so
it now matches upstream for every input below.
"""

import io

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName
from pypdfbox.fontbox.cff.cff_font import CFFFont
from pypdfbox.pdmodel.font.pd_type1c_font import PDType1CFont

_BASE_FONT = COSName.get_pdf_name("BaseFont")
_WIDTHS = COSName.get_pdf_name("Widths")


# ---------- helpers ----------


def _build_cff_bytes(
    widths_by_name: dict[str, int],
    *,
    ps_name: str = "Wave1359CFF",
) -> bytes:
    """Build a minimal CFF with ``.notdef`` plus the named glyphs whose
    advance widths are given by ``widths_by_name``.

    Mirrors the helper used in ``test_pd_type1c_font.py`` but parametrised
    so a caller can vary per-glyph advances and exercise the
    mean-of-glyph-widths branch with non-trivial GID->width variance.
    """
    from fontTools.fontBuilder import FontBuilder
    from fontTools.misc.psCharStrings import T2CharString
    from fontTools.ttLib import TTFont

    fb = FontBuilder(1000, isTTF=False)
    glyph_order = [".notdef", *widths_by_name.keys()]
    fb.setupGlyphOrder(glyph_order)
    # /CharacterMap is not consulted by get_average_character_width's
    # CFF path, but FontBuilder needs *some* cmap entries to validate.
    fb.setupCharacterMap({0x41 + i: name for i, name in enumerate(widths_by_name)})

    def _cs(width: int) -> T2CharString:
        # Leading operand -> Type 2 charstring width-prologue. With
        # defaultWidthX = 0 / nominalWidthX = 0 this produces an
        # extracted width of exactly `width`.
        s = T2CharString()
        s.program = [width, 0, "hmoveto", 100, "vlineto", "endchar"]
        return s

    char_strings = {".notdef": T2CharString()}
    char_strings[".notdef"].program = [0, "endchar"]
    for name, w in widths_by_name.items():
        char_strings[name] = _cs(w)

    fb.setupCFF(
        psName=ps_name,
        fontInfo={"FullName": ps_name},
        charStringsDict=char_strings,
        privateDict={},
    )
    metrics: dict[str, tuple[int, int]] = {".notdef": (0, 0)}
    for name, w in widths_by_name.items():
        metrics[name] = (w, 0)
    fb.setupHorizontalMetrics(metrics)
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupOS2(sTypoAscender=800, sTypoDescender=-200, usWinAscent=800, usWinDescent=200)
    fb.setupNameTable({"familyName": "Wave1359", "styleName": "Regular"})
    fb.setupPost()
    buf = io.BytesIO()
    fb.font.save(buf)
    return bytes(TTFont(io.BytesIO(buf.getvalue())).getTableData("CFF "))


def _inject_font(widths_by_name: dict[str, int]) -> PDType1CFont:
    cff = CFFFont.from_bytes(_build_cff_bytes(widths_by_name))
    font = PDType1CFont(COSDictionary())
    font.set_font_program(cff)
    return font


# ---------- upstream's constant, whatever the font carries ----------


def _with_widths(font: PDType1CFont, *widths: float) -> PDType1CFont:
    font.get_cos_object().set_item(_WIDTHS, COSArray([COSFloat(w) for w in widths]))
    return font


def _standard14() -> PDType1CFont:
    font = PDType1CFont(COSDictionary())
    font.get_cos_object().set_name(_BASE_FONT, "Helvetica")
    return font


def _non_default_em() -> PDType1CFont:
    font = _inject_font({"A": 1024, "B": 2048})
    program = font.get_cff_font()
    assert program is not None
    program._units_per_em = 2048  # type: ignore[attr-defined]
    return font


@pytest.mark.parametrize(
    "make_font",
    [
        pytest.param(lambda: PDType1CFont(), id="empty"),
        pytest.param(
            lambda: _with_widths(PDType1CFont(COSDictionary()), 400.0, 600.0, 0.0, 800.0),
            id="widths",
        ),
        pytest.param(
            lambda: _with_widths(_inject_font({"A": 500, "B": 300}), 100.0, 200.0),
            id="widths_and_program",
        ),
        pytest.param(lambda: _inject_font({"A": 500, "B": 300}), id="program"),
        pytest.param(lambda: _inject_font({"A": 600, "B": 800, "C": 1000}), id="three_glyphs"),
        pytest.param(_standard14, id="standard14"),
        pytest.param(_non_default_em, id="em_2048"),
    ],
)
def test_average_width_is_upstream_constant(make_font) -> None:  # type: ignore[no-untyped-def]
    font = make_font()
    assert font.get_average_character_width() == 500.0
    assert font.get_average_font_width() == 500.0
