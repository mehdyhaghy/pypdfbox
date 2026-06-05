"""Standard-14 (non-embedded, AFM-backed) metric parity for PDType1Font.

Pins values confirmed against the live Apache PDFBox 3.0.7 oracle
(``Std14HeightWidthProbe`` / ``NotdefWidthProbe``) for ``get_height``,
``get_width`` (the ``/Widths`` / ``/MissingWidth`` / Standard-14-AFM
precedence chain), and ``get_average_font_width`` (the upstream override
that ignores ``/Widths`` for the Standard 14).

The hard-coded expectations let these run without the oracle; an opt-in
``@requires_oracle`` differential at the end re-derives them live.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName
from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font

_SUBTYPE = COSName.get_pdf_name("Subtype")
_BASE_FONT = COSName.get_pdf_name("BaseFont")
_FIRST_CHAR = COSName.get_pdf_name("FirstChar")
_LAST_CHAR = COSName.get_pdf_name("LastChar")
_WIDTHS = COSName.get_pdf_name("Widths")


def _font(base_font: str) -> PDType1Font:
    # The oracle (Std14HeightWidthProbe) builds each font via the *direct*
    # ``new PDType1Font(FontName)`` constructor, which assigns WinAnsi to the
    # Latin cores (with an explicit /Encoding write) and the FontSpecific
    # built-in encoding to Symbol / ZapfDingbats. ``PDType1Font.standard14``
    # ports that constructor. A dict-loaded core with NO /Encoding instead
    # reads AdobeStandardEncoding from its AFM (wave-1491 toUnicode split), a
    # different path with different code -> glyph -> metric resolution.
    return PDType1Font.standard14(base_font)


# ---------- get_height (AFM CharMetric BBox height) ----------

# Oracle-pinned getHeight(code) for a spread of codes. Space (32) is 0.
_HEIGHT_EXPECT: dict[str, dict[int, float]] = {
    "Helvetica": {
        32: 0.0, 33: 718.0, 48: 722.0, 65: 718.0, 97: 553.0,
        98: 733.0, 109: 538.0, 200: 929.0, 233: 749.0, 255: 920.0,
    },
    "Times-Bold": {
        32: 0.0, 33: 704.0, 48: 701.0, 65: 690.0, 97: 487.0,
        98: 690.0, 109: 473.0, 200: 923.0, 233: 727.0, 255: 872.0,
    },
    "Symbol": {
        32: 0.0, 33: 689.0, 48: 699.0, 65: 673.0, 97: 518.0,
        98: 964.0, 109: 723.0, 200: 509.0, 233: 1006.0, 255: 0.0,
    },
    "Courier": {
        32: 0.0, 33: 587.0, 48: 637.0, 65: 562.0, 97: 456.0,
        98: 644.0, 109: 441.0, 200: 805.0, 233: 687.0, 255: 777.0,
    },
}


@pytest.mark.parametrize("base_font", list(_HEIGHT_EXPECT))
def test_get_height_matches_afm_char_bbox(base_font: str) -> None:
    font = _font(base_font)
    for code, expected in _HEIGHT_EXPECT[base_font].items():
        assert font.get_height(code) == expected, (base_font, code)


def test_get_height_space_is_zero() -> None:
    # The space glyph has no contours -> zero bbox height across the family.
    for base_font in _HEIGHT_EXPECT:
        assert _font(base_font).get_height(32) == 0.0


# ---------- get_average_font_width (AFM mean, /Widths-blind) ----------

# Oracle-pinned getAverageFontWidth() (4dp) for the non-embedded Standard 14.
_AVG_EXPECT: dict[str, float] = {
    "Helvetica": 542.7714,
    "Times-Bold": 542.2286,
    "Symbol": 588.0316,
    "Courier": 600.0,
}


@pytest.mark.parametrize("base_font,expected", list(_AVG_EXPECT.items()))
def test_get_average_font_width_afm_mean(base_font: str, expected: float) -> None:
    assert round(_font(base_font).get_average_font_width(), 4) == expected


def test_get_average_font_width_ignores_widths_for_standard_14() -> None:
    """Upstream PDType1Font.getAverageFontWidth ignores /Widths for std14.

    Verified against the live oracle: a Helvetica with an explicit
    /Widths of 999/888/777 still reports the AFM mean (542.7714), not the
    /Widths arithmetic mean (888).
    """
    d = COSDictionary()
    d.set_item(_SUBTYPE, COSName.get_pdf_name("Type1"))
    d.set_item(_BASE_FONT, COSName.get_pdf_name("Helvetica"))
    d.set_int(_FIRST_CHAR, 65)
    d.set_int(_LAST_CHAR, 67)
    widths = COSArray()
    for v in (999.0, 888.0, 777.0):
        widths.add(COSFloat(v))
    d.set_item(_WIDTHS, widths)
    font = PDType1Font(d)
    assert round(font.get_average_font_width(), 4) == 542.7714


def test_get_average_font_width_widths_mean_for_non_standard_14() -> None:
    d = COSDictionary()
    d.set_item(_SUBTYPE, COSName.get_pdf_name("Type1"))
    d.set_item(_BASE_FONT, COSName.get_pdf_name("MyCustomFont"))
    d.set_int(_FIRST_CHAR, 65)
    d.set_int(_LAST_CHAR, 67)
    widths = COSArray()
    for v in (999.0, 888.0, 777.0):
        widths.add(COSFloat(v))
    d.set_item(_WIDTHS, widths)
    assert PDType1Font(d).get_average_font_width() == 888.0


# ---------- get_width precedence (/Widths, /MissingWidth, AFM, .notdef) ----------

# Oracle-pinned getWidth(code) for a pure non-embedded Helvetica (no /Widths).
# Codes that map to .notdef in WinAnsi -> 250; WinAnsi control codes mapped to
# `bullet` -> 350; nbspace (160) -> space width 278; sfthyphen (173) -> 333.
_HV_WIDTH_EXPECT: dict[int, float] = {
    0: 250.0, 1: 250.0, 31: 250.0, 32: 278.0, 65: 667.0,
    127: 350.0, 129: 350.0, 141: 350.0, 143: 350.0, 144: 350.0,
    157: 350.0, 160: 278.0, 173: 333.0,
}
# Symbol: codes outside its built-in encoding -> .notdef -> 250.
_SY_WIDTH_EXPECT: dict[int, float] = {
    32: 250.0, 65: 722.0, 97: 631.0, 0: 250.0, 1: 250.0,
    127: 250.0, 200: 768.0, 255: 250.0,
}


def test_get_width_helvetica_notdef_and_control_codes() -> None:
    font = _font("Helvetica")
    for code, expected in _HV_WIDTH_EXPECT.items():
        assert font.get_width(code) == expected, code


def test_get_width_symbol_builtin_encoding() -> None:
    font = _font("Symbol")
    for code, expected in _SY_WIDTH_EXPECT.items():
        assert font.get_width(code) == expected, code


def test_get_width_widths_window_then_missing_width() -> None:
    """/Widths wins inside the window; outside it the synthesized
    descriptor's /MissingWidth (0.0) is returned — NOT the AFM.

    Mirrors upstream PDFont.getWidth: a Standard-14 font auto-synthesizes
    a FontDescriptor from its AFM, so the `fd != null` branch returns
    /MissingWidth (defaulting to 0.0) for any code outside the /Widths
    window rather than falling through to getStandard14Width.
    """
    d = COSDictionary()
    d.set_item(_SUBTYPE, COSName.get_pdf_name("Type1"))
    d.set_item(_BASE_FONT, COSName.get_pdf_name("Helvetica"))
    d.set_int(_FIRST_CHAR, 65)
    d.set_int(_LAST_CHAR, 67)
    widths = COSArray()
    for v in (999.0, 888.0, 777.0):
        widths.add(COSFloat(v))
    d.set_item(_WIDTHS, widths)
    font = PDType1Font(d)
    assert font.get_width(65) == 999.0  # in window
    assert font.get_width(66) == 888.0
    assert font.get_width(67) == 777.0
    assert font.get_width(90) == 0.0  # outside window -> MissingWidth default


# ---------- optional live differential ----------


def test_oracle_std14_height_avg_differential() -> None:
    from tests.oracle.harness import oracle_available, run_probe_text

    if not oracle_available():
        pytest.skip("live PDFBox oracle unavailable")

    text = run_probe_text("Std14HeightWidthProbe")
    current: str | None = None
    for line in text.splitlines():
        parts = line.split("\t")
        if parts[0] == "FONT":
            current = parts[1]
        elif parts[0] == "H" and current in _HEIGHT_EXPECT:
            code = int(parts[1])
            if code in _HEIGHT_EXPECT[current]:
                assert (
                    float(parts[2]) == _HEIGHT_EXPECT[current][code]
                ), (current, code)
        elif parts[0] == "AVG" and current in _AVG_EXPECT:
            assert round(float(parts[1]), 4) == _AVG_EXPECT[current], current
