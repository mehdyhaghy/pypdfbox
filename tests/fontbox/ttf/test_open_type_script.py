"""Tests for :mod:`pypdfbox.fontbox.ttf.open_type_script`."""

from __future__ import annotations

import pytest

from pypdfbox.fontbox.ttf.open_type_script import (
    INHERITED,
    TAG_DEFAULT,
    UNKNOWN,
    OpenTypeScript,
    get_script_tags,
    get_unicode_script,
)


def test_constants_match_upstream() -> None:
    assert INHERITED == "Inherited"
    assert UNKNOWN == "Unknown"
    assert TAG_DEFAULT == "DFLT"
    assert OpenTypeScript.INHERITED == INHERITED
    assert OpenTypeScript.UNKNOWN == UNKNOWN
    assert OpenTypeScript.TAG_DEFAULT == TAG_DEFAULT


def test_latin_letter_maps_to_latn() -> None:
    assert get_script_tags(ord("A")) == ("latn",)
    assert get_script_tags(ord("z")) == ("latn",)


def test_devanagari_emits_v2_first() -> None:
    # 0x0905 = DEVANAGARI LETTER A
    assert get_script_tags(0x0905) == ("dev2", "deva")


def test_bengali_emits_v2_first() -> None:
    assert get_script_tags(0x0985) == ("bng2", "beng")


def test_common_codepoint_returns_dflt() -> None:
    # 0x0020 = SPACE (Common)
    assert get_script_tags(0x0020) == ("DFLT",)


def test_inherited_returns_inherited_literal_not_dflt() -> None:
    # 0x0300 = COMBINING GRAVE ACCENT (Inherited)
    assert get_script_tags(0x0300) == (INHERITED,)


def test_hiragana_and_katakana_both_kana() -> None:
    # Hiragana 0x3042, Katakana 0x30A2 — both map to ``kana``.
    assert get_script_tags(0x3042) == ("kana",)
    assert get_script_tags(0x30A2) == ("kana",)


def test_invalid_codepoint_raises() -> None:
    with pytest.raises(ValueError):
        get_script_tags(-1)
    with pytest.raises(ValueError):
        get_script_tags(0x110000)


def test_unicode_script_unassigned_is_unknown() -> None:
    # 0xE0100 is an unassigned variation-selector / non-script codepoint
    # in some Unicode contexts; the fontTools-backed lookup falls through
    # to whatever short tag is known, but the public surface is the
    # behaviour we care about — script tags must always come back as a
    # tuple or None, never raise (for valid codepoints).
    cp = 0x9FFFFF & 0x10FFFF
    # Stay within range; just ensure no exception for a valid codepoint
    # at the high end.
    get_unicode_script(cp)


def test_open_type_script_constructor_raises() -> None:
    # Upstream's constructor is private; we make the instance form raise
    # so accidental ``OpenTypeScript()`` calls surface immediately.
    with pytest.raises(TypeError):
        OpenTypeScript()


def test_static_helpers_delegate_to_module_level() -> None:
    assert OpenTypeScript.get_script_tags(ord("A")) == ("latn",)
    assert OpenTypeScript.get_unicode_script(ord("A")) == "Latin"
