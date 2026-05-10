from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName
from pypdfbox.pdmodel.font.afm_loader import AfmMetrics, load_standard14, standard14_names
from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font
from pypdfbox.pdmodel.font.standard14_fonts import Standard14Fonts

# ---- canonical AFM values --------------------------------------------------


def test_times_roman_a_advance_width_is_722() -> None:
    """Times-Roman 'A' is the textbook AFM value (Adobe Core 14)."""
    afm = load_standard14("Times-Roman")
    assert afm.get_glyph_width("A") == 722.0


def test_helvetica_m_advance_width_is_833() -> None:
    afm = load_standard14("Helvetica")
    assert afm.get_glyph_width("M") == 833.0


def test_helvetica_bold_h_advance_width_is_722() -> None:
    # Helvetica-Bold 'H' = 722 (cross-check a different font + glyph).
    afm = load_standard14("Helvetica-Bold")
    assert afm.get_glyph_width("H") == 722.0


def test_courier_every_glyph_has_width_600() -> None:
    """All Courier variants are monospaced at 600 units in their AFMs."""
    for name in (
        "Courier",
        "Courier-Bold",
        "Courier-Oblique",
        "Courier-BoldOblique",
    ):
        afm = load_standard14(name)
        widths = {w for w in afm._widths_by_name.values()}
        assert widths == {600.0}, f"{name} widths were {widths}"


def test_symbol_alpha_has_known_width() -> None:
    # Adobe Symbol 'alpha' = 631 (matches the AFM ChyM line).
    afm = load_standard14("Symbol")
    assert afm.get_glyph_width("alpha") == 631.0


def test_zapfdingbats_has_real_glyphs() -> None:
    # ZapfDingbats glyph 'a1' (the scissors at code 0x21) is 974.
    afm = load_standard14("ZapfDingbats")
    assert afm.get_glyph_width("a1") == 974.0


# ---- AFM loader caching ----------------------------------------------------


def test_loading_the_same_standard14_twice_returns_cached_afm() -> None:
    a1 = load_standard14("Times-Roman")
    a2 = load_standard14("Times-Roman")
    assert a1 is a2


def test_standard14fonts_get_afm_returns_same_cached_instance_via_alias() -> None:
    # 'Arial' aliases to 'Helvetica' — both should reach the cached AfmMetrics.
    via_canonical = Standard14Fonts.get_afm("Helvetica")
    via_alias = Standard14Fonts.get_afm("Arial")
    assert via_alias is via_canonical


def test_load_standard14_rejects_unknown_name() -> None:
    with pytest.raises(ValueError):
        load_standard14("NotAFont")


def test_standard14_names_lists_all_14() -> None:
    names = standard14_names()
    assert len(names) == 14
    assert "Times-Roman" in names
    assert "ZapfDingbats" in names


# ---- AfmMetrics.get_font_metrics ------------------------------------------


def test_get_font_metrics_times_roman_matches_published_values() -> None:
    m = load_standard14("Times-Roman").get_font_metrics()
    # Adobe Core 14 published values for Times-Roman.
    assert m["FontName"] == "Times-Roman"
    assert m["FontBBox"] == (-168, -218, 1000, 898)
    assert m["ItalicAngle"] == 0.0
    assert m["Ascent"] == 683.0
    assert m["Descent"] == -217.0
    assert m["CapHeight"] == 662.0
    assert m["XHeight"] == 450.0
    assert m["StemV"] == 84.0
    assert m["IsFixedPitch"] is False


def test_get_font_metrics_courier_is_fixed_pitch() -> None:
    m = load_standard14("Courier").get_font_metrics()
    assert m["IsFixedPitch"] is True


# ---- Standard14Fonts.get_average_widths ------------------------------------


def test_get_average_widths_courier_table_is_uniform_600() -> None:
    """Courier's 256-element table only carries 600 in encoded slots."""
    table = Standard14Fonts.get_average_widths("Courier")
    assert len(table) == 256
    nonzero = {w for w in table if w > 0}
    assert nonzero == {600.0}


def test_get_average_widths_times_roman_a_position_is_722() -> None:
    # StandardEncoding maps 0x41 -> 'A'.
    table = Standard14Fonts.get_average_widths("Times-Roman")
    assert table[0x41] == 722.0


def test_get_average_widths_helvetica_m_position_is_833() -> None:
    table = Standard14Fonts.get_average_widths("Helvetica")
    assert table[0x4D] == 833.0


def test_get_average_widths_returns_independent_copies() -> None:
    """Mutating the returned list must not poison the cache."""
    a = Standard14Fonts.get_average_widths("Helvetica")
    a[0] = 999999.0
    b = Standard14Fonts.get_average_widths("Helvetica")
    assert b[0] != 999999.0


# ---- /Widths override behaviour (PDF 32000-1 §9.6.6.4) ---------------------


def _make_type1(base_font: str, widths: list[int] | None, first: int = 0x41) -> PDType1Font:
    d = COSDictionary()
    d.set_name(COSName.get_pdf_name("BaseFont"), base_font)
    d.set_name(COSName.get_pdf_name("Subtype"), "Type1")
    if widths is not None:
        d.set_int(COSName.get_pdf_name("FirstChar"), first)
        d.set_int(COSName.get_pdf_name("LastChar"), first + len(widths) - 1)
        arr = COSArray()
        for w in widths:
            arr.add(COSInteger.get(w))
        d.set_item(COSName.get_pdf_name("Widths"), arr)
    return PDType1Font(d)


def test_widths_override_wins_over_afm_for_standard14() -> None:
    """A PDF /Widths array overrides the AFM lookup for a Standard 14 font."""
    # Times-Roman 'A' in the AFM = 722. We override with 999.
    font = _make_type1("Times-Roman", widths=[999, 888], first=0x41)
    assert font.get_glyph_width(0x41) == 999.0  # /Widths wins over 722 AFM
    assert font.get_glyph_width(0x42) == 888.0  # /Widths wins for 'B' too


def test_get_glyph_width_falls_back_to_afm_when_no_widths() -> None:
    """No /Widths array -> the Standard 14 AFM supplies the metric."""
    font = _make_type1("Times-Roman", widths=None)
    assert font.get_glyph_width(0x41) == 722.0  # 'A' from the AFM
    assert font.get_glyph_width(0x4D) == 889.0  # 'M' from the AFM


def test_get_glyph_width_falls_back_to_afm_outside_first_last_window() -> None:
    """Codes below /FirstChar or above /LastChar still fall through to AFM."""
    font = _make_type1("Times-Roman", widths=[111], first=0x41)  # only 'A' = 111
    assert font.get_glyph_width(0x41) == 111.0  # inside the window -> override
    # 'M' (0x4D) is past /LastChar so /Widths doesn't apply -> AFM (889).
    assert font.get_glyph_width(0x4D) == 889.0


def test_get_glyph_width_returns_zero_for_non_standard14_without_widths() -> None:
    """Non-Standard-14 with no /Widths -> 0 (matches PDFBox getWidth fallback)."""
    font = _make_type1("MyCustomFont", widths=None)
    assert font.get_glyph_width(0x41) == 0.0


def test_get_glyph_width_alias_resolves_via_standard14() -> None:
    """'Arial' base-font alias still reaches Helvetica's AFM."""
    font = _make_type1("Arial", widths=None)
    # Helvetica 'A' = 667 in the AFM.
    assert font.get_glyph_width(0x41) == 667.0


# ---- AfmMetrics surface ----------------------------------------------------


def test_afm_metrics_has_glyph_reports_unknown_as_false() -> None:
    afm = load_standard14("Times-Roman")
    assert afm.has_glyph("A") is True
    assert afm.has_glyph("totally-not-a-glyph") is False


def test_afm_metrics_get_glyph_width_unknown_is_zero() -> None:
    afm = load_standard14("Times-Roman")
    assert afm.get_glyph_width("totally-not-a-glyph") == 0.0


def test_afm_metrics_get_average_width_is_positive_for_text_fonts() -> None:
    avg = load_standard14("Times-Roman").get_average_width()
    assert avg > 0.0
    # Reasonable range for a Latin text font (approx 470-520).
    assert 400.0 < avg < 600.0


def test_afm_metrics_exposes_canonical_font_name() -> None:
    afm = load_standard14("Helvetica-BoldOblique")
    assert isinstance(afm, AfmMetrics)
    assert afm.get_font_name() == "Helvetica-BoldOblique"
