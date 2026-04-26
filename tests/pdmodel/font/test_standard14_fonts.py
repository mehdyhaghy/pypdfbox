from __future__ import annotations

import pytest

from pypdfbox.pdmodel.font.standard14_fonts import Standard14Fonts

# The 14 canonical names from PDF 32000-1:2008 §9.6.2.2.
_BASE_14 = [
    "Helvetica",
    "Helvetica-Bold",
    "Helvetica-Oblique",
    "Helvetica-BoldOblique",
    "Times-Roman",
    "Times-Bold",
    "Times-Italic",
    "Times-BoldItalic",
    "Courier",
    "Courier-Bold",
    "Courier-Oblique",
    "Courier-BoldOblique",
    "Symbol",
    "ZapfDingbats",
]


# ---------- class constants ----------


def test_class_constants_match_canonical_names() -> None:
    assert Standard14Fonts.HELVETICA == "Helvetica"
    assert Standard14Fonts.HELVETICA_BOLD == "Helvetica-Bold"
    assert Standard14Fonts.HELVETICA_OBLIQUE == "Helvetica-Oblique"
    assert Standard14Fonts.HELVETICA_BOLD_OBLIQUE == "Helvetica-BoldOblique"
    assert Standard14Fonts.TIMES_ROMAN == "Times-Roman"
    assert Standard14Fonts.TIMES_BOLD == "Times-Bold"
    assert Standard14Fonts.TIMES_ITALIC == "Times-Italic"
    assert Standard14Fonts.TIMES_BOLD_ITALIC == "Times-BoldItalic"
    assert Standard14Fonts.COURIER == "Courier"
    assert Standard14Fonts.COURIER_BOLD == "Courier-Bold"
    assert Standard14Fonts.COURIER_OBLIQUE == "Courier-Oblique"
    assert Standard14Fonts.COURIER_BOLD_OBLIQUE == "Courier-BoldOblique"
    assert Standard14Fonts.SYMBOL == "Symbol"
    assert Standard14Fonts.ZAPF_DINGBATS == "ZapfDingbats"


# ---------- containsName / getMappedFontName ----------


@pytest.mark.parametrize("name", _BASE_14)
def test_contains_name_recognises_all_14_base_names(name: str) -> None:
    assert Standard14Fonts.containsName(name) is True


@pytest.mark.parametrize("name", _BASE_14)
def test_get_mapped_font_name_is_identity_for_canonical_names(name: str) -> None:
    assert Standard14Fonts.getMappedFontName(name) == name


def test_contains_name_recognises_arial_alias() -> None:
    assert Standard14Fonts.containsName("Arial") is True


def test_get_mapped_font_name_resolves_arial_to_helvetica() -> None:
    assert Standard14Fonts.getMappedFontName("Arial") == "Helvetica"


def test_get_mapped_font_name_resolves_microsoft_aliases() -> None:
    assert Standard14Fonts.getMappedFontName("TimesNewRoman") == "Times-Roman"
    assert Standard14Fonts.getMappedFontName("CourierNew") == "Courier"
    assert Standard14Fonts.getMappedFontName("ArialMT") == "Helvetica"
    assert Standard14Fonts.getMappedFontName("CourierNewPS-BoldMT") == "Courier-Bold"


def test_lookup_is_case_insensitive_on_input() -> None:
    assert Standard14Fonts.containsName("helvetica") is True
    assert Standard14Fonts.containsName("ARIAL") is True
    # Output is always the exactly-cased canonical name.
    assert Standard14Fonts.getMappedFontName("helvetica-bold") == "Helvetica-Bold"
    assert Standard14Fonts.getMappedFontName("zapfdingbats") == "ZapfDingbats"


def test_unknown_names_are_rejected() -> None:
    assert Standard14Fonts.containsName("NotAFont") is False
    assert Standard14Fonts.containsName(None) is False
    assert Standard14Fonts.getMappedFontName("NotAFont") is None
    assert Standard14Fonts.getMappedFontName(None) is None


# ---------- get_average_widths ----------


def test_courier_widths_are_600_across_256_slots() -> None:
    widths = Standard14Fonts.get_average_widths("Courier")
    assert isinstance(widths, list)
    assert len(widths) == 256
    assert all(w == 600.0 for w in widths)


@pytest.mark.parametrize("name", ["Courier-Bold", "Courier-Oblique", "Courier-BoldOblique"])
def test_all_courier_variants_are_monospace_600(name: str) -> None:
    widths = Standard14Fonts.get_average_widths(name)
    assert len(widths) == 256
    assert all(w == 600.0 for w in widths)


@pytest.mark.parametrize(
    "name",
    [
        "Helvetica",
        "Helvetica-Bold",
        "Times-Roman",
        "Times-BoldItalic",
        "Symbol",
        "ZapfDingbats",
    ],
)
def test_proportional_families_use_500_placeholder(name: str) -> None:
    widths = Standard14Fonts.get_average_widths(name)
    assert len(widths) == 256
    assert all(w == 500.0 for w in widths)


def test_get_average_widths_resolves_alias() -> None:
    # Arial alias should reach Helvetica's table.
    arial = Standard14Fonts.get_average_widths("Arial")
    helvetica = Standard14Fonts.get_average_widths("Helvetica")
    assert arial == helvetica


def test_get_average_widths_rejects_unknown_name() -> None:
    with pytest.raises(ValueError):
        Standard14Fonts.get_average_widths("NotAFont")


# ---------- get_font_descriptor ----------


def test_get_font_descriptor_for_times_roman_has_expected_shape() -> None:
    fd = Standard14Fonts.get_font_descriptor("Times-Roman")
    assert isinstance(fd, dict)
    assert fd["FontName"] == "Times-Roman"
    assert isinstance(fd["Flags"], int) and fd["Flags"] > 0
    assert isinstance(fd["FontBBox"], list) and len(fd["FontBBox"]) == 4
    assert all(isinstance(v, float) for v in fd["FontBBox"])
    # Numeric metrics are floats.
    for key in ("ItalicAngle", "Ascent", "Descent", "CapHeight", "XHeight", "StemV"):
        assert isinstance(fd[key], float), key
    # Times-Roman has positive ascent and a sane descent.
    assert fd["Ascent"] > 0
    assert fd["Descent"] < 0


def test_get_font_descriptor_resolves_alias_to_canonical_font_name() -> None:
    fd = Standard14Fonts.get_font_descriptor("Arial")
    assert fd["FontName"] == "Helvetica"


def test_get_font_descriptor_courier_is_fixed_pitch() -> None:
    fd = Standard14Fonts.get_font_descriptor("Courier")
    # Bit 0 of Flags is FixedPitch (PDF 32000-1:2008 §9.8.2 Table 123).
    assert fd["Flags"] & 0b1 == 0b1


def test_get_font_descriptor_symbol_is_symbolic() -> None:
    fd = Standard14Fonts.get_font_descriptor("Symbol")
    # Bit 2 of Flags is Symbolic.
    assert fd["Flags"] & 0b100 == 0b100


def test_get_font_descriptor_italic_variants_have_negative_italic_angle() -> None:
    for name in ("Helvetica-Oblique", "Times-Italic", "Times-BoldItalic", "Courier-Oblique"):
        fd = Standard14Fonts.get_font_descriptor(name)
        assert fd["ItalicAngle"] < 0, name


def test_get_font_descriptor_rejects_unknown_name() -> None:
    with pytest.raises(ValueError):
        Standard14Fonts.get_font_descriptor("NotAFont")
