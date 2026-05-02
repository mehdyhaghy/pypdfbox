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
