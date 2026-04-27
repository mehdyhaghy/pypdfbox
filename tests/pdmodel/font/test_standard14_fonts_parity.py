"""Upstream-API parity tests for ``Standard14Fonts``.

These cover the snake_case method surface that mirrors PDFBox's
``org.apache.pdfbox.pdmodel.font.Standard14Fonts``: ``contains_name``,
``is_standard_14``, ``get_mapped_font_name``, ``get_names``, ``get_aliases``,
``get_afm``, ``get_glyph_width``, ``get_average_widths``, ``get_font_metrics``
(raw AFM numerics) and the per-font class constants.
"""

from __future__ import annotations

import pytest

from pypdfbox.pdmodel.font.afm_loader import AfmMetrics
from pypdfbox.pdmodel.font.standard14_fonts import Standard14Fonts

# The 14 canonical names (PDF 32000-1:2008 §9.6.2.2).
_BASE_14 = {
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
}


# ---------- contains_name / is_standard_14 (alias agreement) ----------


@pytest.mark.parametrize("name", sorted(_BASE_14))
def test_contains_name_and_is_standard_14_agree_for_canonical(name: str) -> None:
    assert Standard14Fonts.contains_name(name) is True
    assert Standard14Fonts.is_standard_14(name) is True


@pytest.mark.parametrize(
    "name", ["Arial", "ArialMT", "TimesNewRoman", "CourierNewPS-BoldMT"]
)
def test_contains_name_and_is_standard_14_agree_for_aliases(name: str) -> None:
    assert Standard14Fonts.contains_name(name) == Standard14Fonts.is_standard_14(name)
    assert Standard14Fonts.is_standard_14(name) is True


@pytest.mark.parametrize("name", ["NotAFont", "", None])
def test_contains_name_and_is_standard_14_agree_for_unknown(name: str | None) -> None:
    assert Standard14Fonts.contains_name(name) == Standard14Fonts.is_standard_14(name)
    assert Standard14Fonts.is_standard_14(name) is False


# ---------- get_mapped_font_name ----------


def test_get_mapped_font_name_arial_resolves_to_helvetica() -> None:
    assert Standard14Fonts.get_mapped_font_name("ArialMT") == "Helvetica"


def test_get_mapped_font_name_returns_none_for_unknown() -> None:
    assert Standard14Fonts.get_mapped_font_name("NotAFont") is None
    assert Standard14Fonts.get_mapped_font_name(None) is None


@pytest.mark.parametrize("name", sorted(_BASE_14))
def test_get_mapped_font_name_is_identity_for_canonical(name: str) -> None:
    assert Standard14Fonts.get_mapped_font_name(name) == name


def test_get_mapped_font_name_lookup_is_case_insensitive() -> None:
    assert Standard14Fonts.get_mapped_font_name("arialmt") == "Helvetica"
    assert Standard14Fonts.get_mapped_font_name("HELVETICA-BOLD") == "Helvetica-Bold"


# ---------- get_names ----------


def test_get_names_returns_exactly_the_14_canonical_names() -> None:
    names = Standard14Fonts.get_names()
    assert isinstance(names, set)
    assert len(names) == 14
    assert names == _BASE_14


def test_get_names_returns_a_defensive_copy() -> None:
    names = Standard14Fonts.get_names()
    names.add("BogusFont")
    # A second call must not see the mutation.
    assert "BogusFont" not in Standard14Fonts.get_names()


# ---------- get_aliases ----------


def test_get_aliases_maps_arialmt_to_helvetica() -> None:
    aliases = Standard14Fonts.get_aliases()
    assert isinstance(aliases, dict)
    assert aliases["ArialMT"] == "Helvetica"


def test_get_aliases_values_are_canonical_names() -> None:
    aliases = Standard14Fonts.get_aliases()
    assert aliases  # not empty
    for alias, canonical in aliases.items():
        assert canonical in _BASE_14, f"alias {alias!r} -> non-canonical {canonical!r}"


def test_get_aliases_returns_a_defensive_copy() -> None:
    aliases = Standard14Fonts.get_aliases()
    aliases["BogusAlias"] = "Helvetica"
    assert "BogusAlias" not in Standard14Fonts.get_aliases()


# ---------- get_afm ----------


def test_get_afm_helvetica_returns_afm_metrics() -> None:
    afm = Standard14Fonts.get_afm("Helvetica")
    assert isinstance(afm, AfmMetrics)
    assert afm.get_font_name() == "Helvetica"


def test_get_afm_resolves_alias() -> None:
    via_alias = Standard14Fonts.get_afm("ArialMT")
    via_canonical = Standard14Fonts.get_afm("Helvetica")
    # Cached singletons — same instance.
    assert via_alias is via_canonical


def test_get_afm_rejects_unknown_name() -> None:
    with pytest.raises(ValueError):
        Standard14Fonts.get_afm("NotAFont")


# ---------- get_glyph_width ----------


def test_get_glyph_width_courier_is_monospace_600() -> None:
    # All defined glyphs in any Courier variant share advance 600.
    assert Standard14Fonts.get_glyph_width("Courier", "A") == 600.0
    assert Standard14Fonts.get_glyph_width("Courier", "space") == 600.0


def test_get_glyph_width_unknown_glyph_is_zero() -> None:
    assert Standard14Fonts.get_glyph_width("Helvetica", "doesNotExist") == 0.0


# ---------- get_font_metrics (raw AFM numerics) ----------


def test_get_font_metrics_helvetica_returns_dict_with_expected_keys() -> None:
    metrics = Standard14Fonts.get_font_metrics("Helvetica")
    assert isinstance(metrics, dict)
    for key in (
        "FontName",
        "FontBBox",
        "ItalicAngle",
        "Ascent",
        "Descent",
        "CapHeight",
        "XHeight",
        "StemV",
        "IsFixedPitch",
    ):
        assert key in metrics, key
    assert metrics["FontName"] == "Helvetica"
    # Helvetica is proportional.
    assert metrics["IsFixedPitch"] is False


def test_get_font_metrics_courier_is_fixed_pitch() -> None:
    metrics = Standard14Fonts.get_font_metrics("Courier")
    assert metrics is not None
    assert metrics["IsFixedPitch"] is True


def test_get_font_metrics_returns_none_for_unknown() -> None:
    assert Standard14Fonts.get_font_metrics("NotAFont") is None


def test_get_font_metrics_resolves_alias_to_canonical_font_name() -> None:
    metrics = Standard14Fonts.get_font_metrics("ArialMT")
    assert metrics is not None
    assert metrics["FontName"] == "Helvetica"


# ---------- class-level FontName constants ----------


def test_class_constants_cover_all_14_canonical_names() -> None:
    constants = {
        Standard14Fonts.HELVETICA,
        Standard14Fonts.HELVETICA_BOLD,
        Standard14Fonts.HELVETICA_OBLIQUE,
        Standard14Fonts.HELVETICA_BOLD_OBLIQUE,
        Standard14Fonts.TIMES_ROMAN,
        Standard14Fonts.TIMES_BOLD,
        Standard14Fonts.TIMES_ITALIC,
        Standard14Fonts.TIMES_BOLD_ITALIC,
        Standard14Fonts.COURIER,
        Standard14Fonts.COURIER_BOLD,
        Standard14Fonts.COURIER_OBLIQUE,
        Standard14Fonts.COURIER_BOLD_OBLIQUE,
        Standard14Fonts.SYMBOL,
        Standard14Fonts.ZAPF_DINGBATS,
    }
    assert constants == _BASE_14
