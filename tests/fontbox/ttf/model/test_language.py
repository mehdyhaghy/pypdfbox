"""Hand-written tests for :class:`pypdfbox.fontbox.ttf.model.Language`."""

from __future__ import annotations

from pypdfbox.fontbox.ttf.model import Language


def test_known_languages_have_script_names() -> None:
    assert Language.BENGALI.get_script_names() == ("bng2", "beng")
    assert Language.DEVANAGARI.get_script_names() == ("dev2", "deva")
    assert Language.GUJARATI.get_script_names() == ("gjr2", "gujr")
    assert Language.LATIN.get_script_names() == ("latn",)
    assert Language.DFLT.get_script_names() == ("DFLT",)


def test_unspecified_has_empty_script_names() -> None:
    assert Language.UNSPECIFIED.get_script_names() == ()


def test_unspecified_is_last_entry() -> None:
    """Order matters — :class:`GlyphSubstitutionDataExtractor` iterates
    ``Language`` declarations in order to find a supported script."""
    assert list(Language)[-1] is Language.UNSPECIFIED


def test_language_values_are_unique() -> None:
    names = [lang.name for lang in Language]
    assert len(names) == len(set(names))
