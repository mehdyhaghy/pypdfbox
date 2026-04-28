from __future__ import annotations

from pypdfbox.fontbox.encoding import GlyphList

# -- to_unicode --------------------------------------------------------------

def test_to_unicode_ascii_letter() -> None:
    assert GlyphList.get_default().to_unicode("A") == "A"


def test_to_unicode_aacute() -> None:
    assert GlyphList.get_default().to_unicode("Aacute") == "Á"


def test_to_unicode_none_input() -> None:
    assert GlyphList.get_default().to_unicode(None) is None


# -- name_to_code_points (alias) ---------------------------------------------

def test_name_to_code_points_matches_to_unicode() -> None:
    g = GlyphList.get_default()
    assert g.name_to_code_points("A") == g.to_unicode("A") == "A"


def test_name_to_code_points_ligature() -> None:
    # AGL: fi -> U+FB01 (single codepoint mapping)
    assert GlyphList.get_default().name_to_code_points("fi") == "ﬁ"


# -- code_point_to_name / code_point_to_string -------------------------------

def test_code_point_to_name_basic() -> None:
    assert GlyphList.get_default().code_point_to_name(0x41) == "A"


def test_code_point_to_name_aacute() -> None:
    assert GlyphList.get_default().code_point_to_name(0x00C1) == "Aacute"


def test_code_point_to_name_unknown_returns_none() -> None:
    # U+E000 is in the Private Use Area and not present in AGL.
    assert GlyphList.get_default().code_point_to_name(0xE000) is None


def test_code_point_to_string_alias() -> None:
    g = GlyphList.get_default()
    assert g.code_point_to_string(0x41) == g.code_point_to_name(0x41) == "A"


def test_code_point_to_name_invalid_returns_none() -> None:
    assert GlyphList.get_default().code_point_to_name(-1) is None
    assert GlyphList.get_default().code_point_to_name(0x110000) is None


# -- factories ---------------------------------------------------------------

def test_get_default_returns_glyph_list_singleton() -> None:
    assert isinstance(GlyphList.get_default(), GlyphList)
    assert GlyphList.get_default() is GlyphList.DEFAULT
    assert GlyphList.get_default() is GlyphList.get_adobe_glyph_list()


def test_get_zapf_dingbats_returns_glyph_list_singleton() -> None:
    assert isinstance(GlyphList.get_zapf_dingbats(), GlyphList)
    assert GlyphList.get_zapf_dingbats() is GlyphList.ZAPF_DINGBATS


# -- is_unicode_lookup -------------------------------------------------------

def test_is_unicode_lookup_uni_form() -> None:
    assert GlyphList.is_unicode_lookup("uni00A1") is True
    assert GlyphList.is_unicode_lookup("uni0041") is True


def test_is_unicode_lookup_short_u_form() -> None:
    assert GlyphList.is_unicode_lookup("u00A1") is True
    assert GlyphList.is_unicode_lookup("u1F600") is True
    assert GlyphList.is_unicode_lookup("u01F600") is True


def test_is_unicode_lookup_rejects_non_pattern() -> None:
    assert GlyphList.is_unicode_lookup("A") is False
    assert GlyphList.is_unicode_lookup("Aacute") is False
    assert GlyphList.is_unicode_lookup("uniZZZZ") is False
    assert GlyphList.is_unicode_lookup("") is False
    assert GlyphList.is_unicode_lookup(None) is False


# -- get_or_unicode_lookup ---------------------------------------------------

def test_get_or_unicode_lookup_known_name() -> None:
    assert GlyphList.get_default().get_or_unicode_lookup("A") == "A"


def test_get_or_unicode_lookup_synthesized_uni() -> None:
    # uni0041 is not in AGL as a literal name; falls back to synthesized lookup.
    assert GlyphList.get_default().get_or_unicode_lookup("uni0041") == "A"


def test_get_or_unicode_lookup_unknown_returns_none() -> None:
    assert (
        GlyphList.get_default().get_or_unicode_lookup("definitely_not_a_glyph")
        is None
    )


def test_get_or_unicode_lookup_none_returns_none() -> None:
    assert GlyphList.get_default().get_or_unicode_lookup(None) is None


# -- unicode_to_name ---------------------------------------------------------

def test_unicode_to_name_matches_sequence_to_name() -> None:
    g = GlyphList.get_default()
    assert g.unicode_to_name("A") == g.sequence_to_name("A") == "A"
    assert g.unicode_to_name("Á") == "Aacute"


def test_unicode_to_name_ligature() -> None:
    assert GlyphList.get_default().unicode_to_name("ﬁ") == "fi"


def test_unicode_to_name_unknown_returns_notdef() -> None:
    assert GlyphList.get_default().unicode_to_name("\ue000") == ".notdef"
    assert GlyphList.get_default().unicode_to_name(None) == ".notdef"
