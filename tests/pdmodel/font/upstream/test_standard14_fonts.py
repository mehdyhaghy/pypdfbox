"""Ported tests for :class:`Standard14Fonts`.

Translated from the upstream PDFBox 3.0.x JUnit suite at
``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/font/Standard14FontsTest.java``.

The upstream suite covers three concerns:

1. ``containsName`` recognises the 14 canonical PostScript names and the
   well-known substitute aliases (Arial / TimesNewRoman / CourierNew
   branches plus ``-PS`` / ``-MT`` variants).
2. ``getMappedFontName`` rewrites every alias to its canonical form.
3. ``getAFM`` returns a non-null parsed AFM for every canonical name.

The hand-written suites (``test_standard14_fonts.py`` and
``test_standard14_fonts_parity.py``) cover the snake_case API and the
font-descriptor / width-table machinery; this module focuses on the
upstream-named camelCase surface and the alias inventory.
"""

from __future__ import annotations

import pytest

from pypdfbox.pdmodel.font.afm_loader import AfmMetrics
from pypdfbox.pdmodel.font.standard14_fonts import Standard14Fonts

# The 14 canonical PostScript names (PDF 32000-1:2008 §9.6.2.2).
_BASE_14: tuple[str, ...] = (
    "Times-Roman",
    "Times-Bold",
    "Times-Italic",
    "Times-BoldItalic",
    "Helvetica",
    "Helvetica-Bold",
    "Helvetica-Oblique",
    "Helvetica-BoldOblique",
    "Courier",
    "Courier-Bold",
    "Courier-Oblique",
    "Courier-BoldOblique",
    "Symbol",
    "ZapfDingbats",
)


# ---------- containsName ----------


@pytest.mark.parametrize("name", _BASE_14)
def test_contains_name_for_canonical_names(name: str) -> None:
    """``containsName`` returns true for each of the 14 canonical names.

    Ports ``Standard14FontsTest.testContainsName``.
    """
    assert Standard14Fonts.contains_name(name) is True


@pytest.mark.parametrize(
    ("alias", "canonical"),
    [
        # Arial branch.
        ("Arial", "Helvetica"),
        ("Arial,Bold", "Helvetica-Bold"),
        ("Arial,Italic", "Helvetica-Oblique"),
        ("Arial,BoldItalic", "Helvetica-BoldOblique"),
        ("ArialMT", "Helvetica"),
        ("Arial-BoldMT", "Helvetica-Bold"),
        ("Arial-ItalicMT", "Helvetica-Oblique"),
        ("Arial-BoldItalicMT", "Helvetica-BoldOblique"),
        # TimesNewRoman branch.
        ("TimesNewRoman", "Times-Roman"),
        ("TimesNewRoman,Bold", "Times-Bold"),
        ("TimesNewRoman,Italic", "Times-Italic"),
        ("TimesNewRoman,BoldItalic", "Times-BoldItalic"),
        ("TimesNewRomanPSMT", "Times-Roman"),
        ("TimesNewRomanPS-BoldMT", "Times-Bold"),
        ("TimesNewRomanPS-ItalicMT", "Times-Italic"),
        ("TimesNewRomanPS-BoldItalicMT", "Times-BoldItalic"),
        # CourierNew branch.
        ("CourierNew", "Courier"),
        ("CourierNew,Bold", "Courier-Bold"),
        ("CourierNew,Italic", "Courier-Oblique"),
        ("CourierNew,BoldItalic", "Courier-BoldOblique"),
        ("CourierNewPSMT", "Courier"),
        ("CourierNewPS-BoldMT", "Courier-Bold"),
        ("CourierNewPS-ItalicMT", "Courier-Oblique"),
        ("CourierNewPS-BoldItalicMT", "Courier-BoldOblique"),
    ],
)
def test_contains_name_for_aliases(alias: str, canonical: str) -> None:
    """``containsName`` recognises every well-known alias.

    Ports ``Standard14FontsTest.testContainsName`` (alias half).
    """
    assert Standard14Fonts.contains_name(alias) is True
    # Round-trip parity — the alias must rewrite to the right canonical name.
    assert Standard14Fonts.get_mapped_font_name(alias) == canonical


def test_contains_name_returns_false_for_unknown() -> None:
    """``containsName`` returns false for non-Standard-14 names.

    Ports ``Standard14FontsTest.testContainsName`` (negative half).
    """
    assert Standard14Fonts.contains_name("NotARealFontName") is False


# ---------- getMappedFontName ----------


@pytest.mark.parametrize("name", _BASE_14)
def test_get_mapped_font_name_is_identity_for_canonical(name: str) -> None:
    """``getMappedFontName`` returns the canonical name unchanged.

    Ports ``Standard14FontsTest.testGetMappedFontName``.
    """
    assert Standard14Fonts.get_mapped_font_name(name) == name


# ---------- getAFM ----------


@pytest.mark.parametrize("name", _BASE_14)
def test_get_afm_returns_parsed_metrics_for_each_canonical(name: str) -> None:
    """``getAFM`` returns a parsed :class:`AfmMetrics` for every canonical name.

    Ports ``Standard14FontsTest.testGetAFM`` — upstream asserts the result
    is non-null; we additionally assert the parsed font name round-trips.
    """
    afm = Standard14Fonts.get_afm(name)
    assert isinstance(afm, AfmMetrics)
    assert afm.get_font_name() == name


def test_get_afm_caches_per_canonical_name() -> None:
    """Two calls with the same canonical name share an instance.

    Mirrors upstream's parsed-once-then-cached contract on
    ``Standard14Fonts.get_afm``.
    """
    first = Standard14Fonts.get_afm("Helvetica")
    second = Standard14Fonts.get_afm("Helvetica")
    assert first is second


def test_get_afm_caches_through_alias() -> None:
    """Looking up via an alias hits the same cached instance.

    The alias map normalises before consulting the AFM cache, so
    ``getAFM("Arial")`` and ``getAFM("Helvetica")`` return the same
    instance.
    """
    via_alias = Standard14Fonts.get_afm("Arial")
    via_canonical = Standard14Fonts.get_afm("Helvetica")
    assert via_alias is via_canonical


# ---------- getMappedFont ----------


@pytest.mark.parametrize("name", _BASE_14)
def test_get_mapped_font_returns_a_wrapper_for_each_canonical(name: str) -> None:
    """``getMappedFont`` returns a substitute wrapper for every canonical name.

    Ports the spirit of upstream's private ``getMappedFont(FontName)``
    accessor (Standard14Fonts.java line 245).
    """
    wrapper = Standard14Fonts.get_mapped_font(name)
    assert wrapper is not None
    # The wrapper is the FontBoxFont protocol — name round-trips through it.
    assert wrapper.get_name() == name


def test_get_mapped_font_caches_per_canonical_name() -> None:
    """Two calls with the same canonical name share a wrapper instance.

    Mirrors upstream's ``GENERIC_FONTS`` EnumMap caching contract.
    """
    first = Standard14Fonts.get_mapped_font("Helvetica")
    second = Standard14Fonts.get_mapped_font("Helvetica")
    assert first is second


def test_get_mapped_font_resolves_alias_to_canonical_wrapper() -> None:
    """``Arial`` lookup returns the same wrapper as ``Helvetica``."""
    via_alias = Standard14Fonts.get_mapped_font("Arial")
    via_canonical = Standard14Fonts.get_mapped_font("Helvetica")
    assert via_alias is via_canonical


# ---------- getGlyphPath ----------


def test_get_glyph_path_for_notdef_returns_empty_path() -> None:
    """``.notdef`` short-circuits — upstream returns ``new GeneralPath()``.

    Ports the upstream check at Standard14Fonts.java line 274.
    """
    path = Standard14Fonts.get_glyph_path("Helvetica", ".notdef")
    assert path == []


def test_get_glyph_path_returns_list_for_unknown_glyph() -> None:
    """Unknown glyph names yield an empty path (upstream trailing return).

    Ports the upstream tail at Standard14Fonts.java line 306 (``return
    new GeneralPath();``). The bundled ``Standard14FontWrapper`` carries
    no outlines, so any name will hit this branch in pypdfbox.
    """
    path = Standard14Fonts.get_glyph_path("Helvetica", "NoSuchGlyph")
    assert path == []


def test_get_glyph_path_rejects_unknown_font_with_empty_path() -> None:
    """Unknown font name returns ``[]`` — pypdfbox swallows the upstream
    ``IllegalArgumentException`` here for the path API since drawing
    nothing matches the upstream end-state."""
    assert Standard14Fonts.get_glyph_path("NotAFont", "A") == []


# ---------- loadMetrics ----------


@pytest.mark.parametrize("name", _BASE_14)
def test_load_metrics_returns_parsed_metrics_for_each_canonical(name: str) -> None:
    """``loadMetrics`` parses each Standard 14 AFM and caches it.

    Ports the upstream private ``loadMetrics(FontName)`` accessor
    (Standard14Fonts.java line 129).
    """
    metrics = Standard14Fonts.load_metrics(name)
    assert isinstance(metrics, AfmMetrics)
    assert metrics.get_font_name() == name


def test_load_metrics_rejects_aliases() -> None:
    """The upstream private form takes a ``FontName`` enum, so the alias
    string is not a valid input — pypdfbox surfaces a ``ValueError``."""
    with pytest.raises(ValueError, match="canonical Standard 14"):
        Standard14Fonts.load_metrics("Arial")


# ---------- mapName ----------


def test_map_name_registers_a_new_alias() -> None:
    """``mapName(alias, FontName)`` adds a new alias to the lookup table.

    Ports the upstream private ``mapName(String, FontName)`` overload
    (Standard14Fonts.java line 165).
    """
    try:
        Standard14Fonts.map_name("HelveticaParityAlias", "Helvetica")
        assert Standard14Fonts.contains_name("HelveticaParityAlias") is True
        assert (
            Standard14Fonts.get_mapped_font_name("HelveticaParityAlias")
            == "Helvetica"
        )
    finally:
        # Restore the pre-test state so other tests aren't affected.
        from pypdfbox.pdmodel.font.standard14_fonts import (
            _ALIASES,
            _NAME_LOOKUP,
        )

        _ALIASES.pop("HelveticaParityAlias", None)
        _NAME_LOOKUP.pop("helveticaparityalias", None)


def test_map_name_rejects_unknown_canonical_target() -> None:
    """The target must be a Standard 14 canonical name."""
    with pytest.raises(ValueError, match="canonical Standard 14"):
        Standard14Fonts.map_name("MyAlias", "NotAFont")


# ---------- getGlyphList ----------


def test_get_glyph_list_for_zapf_dingbats_picks_zapf_list() -> None:
    """ZapfDingbats picks the dedicated Zapf glyph list.

    Ports upstream's private ``getGlyphList(FontName)`` selector
    (Standard14Fonts.java line 309).
    """
    from pypdfbox.fontbox.encoding.glyph_list import GlyphList

    assert (
        Standard14Fonts.get_glyph_list("ZapfDingbats")
        is GlyphList.get_zapf_dingbats()
    )


@pytest.mark.parametrize(
    "name",
    [
        "Helvetica",
        "Times-Roman",
        "Courier",
        "Symbol",
    ],
)
def test_get_glyph_list_for_non_zapf_picks_adobe_list(name: str) -> None:
    """Every Standard 14 except ZapfDingbats picks the Adobe Glyph List."""
    from pypdfbox.fontbox.encoding.glyph_list import GlyphList

    assert (
        Standard14Fonts.get_glyph_list(name) is GlyphList.get_adobe_glyph_list()
    )


# ---------- FontName enum ----------


def test_font_name_enum_is_exposed_as_nested_attribute() -> None:
    """``Standard14Fonts.FontName`` mirrors the upstream public nested enum
    (Standard14Fonts.java line 317). Same identity as the top-level alias."""
    from pypdfbox.pdmodel.font.standard14_fonts import FontName

    assert Standard14Fonts.FontName is FontName


@pytest.mark.parametrize("name", _BASE_14)
def test_font_name_enum_has_constant_for_each_canonical_name(name: str) -> None:
    """Every canonical PostScript name has a ``FontName`` constant whose
    ``getName()`` round-trips. Mirrors upstream
    ``Standard14Fonts.FontName.getName`` (line 341)."""
    matches = [
        m for m in Standard14Fonts.FontName if m.get_name() == name
    ]
    assert len(matches) == 1


def test_font_name_to_string_returns_postscript_name() -> None:
    """``toString()`` returns the PostScript name (Standard14Fonts.java
    line 347). Both ``str()`` and the snake_case ``to_string()`` match."""
    helvetica = Standard14Fonts.FontName.HELVETICA
    assert str(helvetica) == "Helvetica"
    assert helvetica.to_string() == "Helvetica"


def test_font_name_count_matches_14() -> None:
    """The enum has exactly 14 constants — the Standard 14 fonts."""
    assert len(list(Standard14Fonts.FontName)) == 14


def test_contains_name_accepts_font_name_enum() -> None:
    """The lookup methods accept a ``FontName`` enum value transparently
    (mirrors upstream's ``FontName``-typed overloads)."""
    assert Standard14Fonts.contains_name(Standard14Fonts.FontName.HELVETICA) is True
    assert Standard14Fonts.contains_name(Standard14Fonts.FontName.SYMBOL) is True


def test_get_mapped_font_name_accepts_font_name_enum() -> None:
    """``getMappedFontName`` accepts an enum and returns the canonical name."""
    assert (
        Standard14Fonts.get_mapped_font_name(Standard14Fonts.FontName.HELVETICA_BOLD)
        == "Helvetica-Bold"
    )
