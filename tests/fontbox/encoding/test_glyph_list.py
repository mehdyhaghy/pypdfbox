from __future__ import annotations

from pypdfbox.fontbox.encoding import GlyphList


def test_singletons_exist() -> None:
    assert GlyphList.DEFAULT is GlyphList.get_adobe_glyph_list()
    assert GlyphList.ZAPF_DINGBATS is GlyphList.get_zapf_dingbats()


def test_default_basic_lookups() -> None:
    g = GlyphList.DEFAULT
    assert g.to_unicode("A") == "A"
    assert g.to_unicode("space") == " "
    assert g.to_unicode("Aacute") == "Á"
    assert g.to_unicode("zero") == "0"


def test_default_multi_codepoint_entry() -> None:
    g = GlyphList.DEFAULT
    # "fi" is a ligature mapped to U+FB01
    assert g.to_unicode("fi") == "ﬁ"


def test_unknown_returns_none() -> None:
    g = GlyphList.DEFAULT
    assert g.to_unicode("definitely_not_a_glyph") is None


def test_none_input_returns_none() -> None:
    g = GlyphList.DEFAULT
    assert g.to_unicode(None) is None


def test_suffix_strip() -> None:
    g = GlyphList.DEFAULT
    # "A.alt" should fall back to "A"
    assert g.to_unicode("A.alt") == "A"
    assert g.to_unicode("space.foo") == " "


def test_uniXXXX_synthesis() -> None:
    g = GlyphList.DEFAULT
    assert g.to_unicode("uni0041") == "A"
    assert g.to_unicode("uni00FC") == "ü"


def test_uXXXX_synthesis() -> None:
    g = GlyphList.DEFAULT
    assert g.to_unicode("u0041") == "A"
    assert g.to_unicode("u00FC") == "ü"


def test_uniXXXX_surrogate_area_returns_none() -> None:
    g = GlyphList.DEFAULT
    # surrogate range D800..DFFF must be rejected
    assert g.to_unicode("uniD800") is None
    assert g.to_unicode("uniDFFF") is None


def test_uniXXXX_invalid_hex_returns_none() -> None:
    g = GlyphList.DEFAULT
    assert g.to_unicode("uniZZZZ") is None
    assert g.to_unicode("uZZZZ") is None


def test_uniXXXX_cached_on_second_call() -> None:
    g = GlyphList.DEFAULT
    a = g.to_unicode("uni4E00")
    b = g.to_unicode("uni4E00")
    assert a == b == "一"


def test_zapf_dingbats_basic_lookup() -> None:
    g = GlyphList.ZAPF_DINGBATS
    # zapfdingbats.txt: a1;2701  -> U+2701
    assert g.to_unicode("a1") == "✁"
    # space is an entry in zapf dingbats list too
    assert g.to_unicode("space") == " "


def test_zapf_dingbats_only_has_zd_entries() -> None:
    g = GlyphList.ZAPF_DINGBATS
    # "Aacute" is in AGL but not Zapf Dingbats
    assert g.to_unicode("Aacute") is None


def test_default_size_is_4281() -> None:
    g = GlyphList.DEFAULT
    assert len(g._name_to_unicode) == 4281


def test_zapf_dingbats_size_is_202() -> None:
    g = GlyphList.ZAPF_DINGBATS
    assert len(g._name_to_unicode) == 202


# -- new factory aliases ----------------------------------------------------


def test_get_default_glyph_list_returns_agl_singleton() -> None:
    assert GlyphList.get_default_glyph_list() is GlyphList.DEFAULT
    assert GlyphList.get_default_glyph_list() is GlyphList.get_adobe_glyph_list()


# -- unicode_for_name (alias) -----------------------------------------------


def test_unicode_for_name_matches_to_unicode() -> None:
    g = GlyphList.DEFAULT
    assert g.unicode_for_name("A") == g.to_unicode("A") == "A"
    assert g.unicode_for_name("Aacute") == "Á"
    assert g.unicode_for_name(None) is None
    assert g.unicode_for_name("definitely_not_a_glyph") is None


# -- code_point_for_glyph_name ----------------------------------------------


def test_code_point_for_glyph_name_basic() -> None:
    g = GlyphList.DEFAULT
    assert g.code_point_for_glyph_name("A") == 0x41
    assert g.code_point_for_glyph_name("Aacute") == 0x00C1
    assert g.code_point_for_glyph_name("space") == 0x20


def test_code_point_for_glyph_name_unknown_returns_none() -> None:
    assert GlyphList.DEFAULT.code_point_for_glyph_name("does_not_exist") is None


def test_code_point_for_glyph_name_none_returns_none() -> None:
    assert GlyphList.DEFAULT.code_point_for_glyph_name(None) is None


def test_code_point_for_glyph_name_ligature_returns_none() -> None:
    # AGL has multi-codepoint ligature entries (e.g. "ffi" -> "ﬃ" is one
    # codepoint, but some entries are multi-codepoint). Pick one that maps
    # to multiple code points.
    g = GlyphList.DEFAULT
    # Find a multi-codepoint glyph name in AGL
    multi = next(
        (n for n, v in g._name_to_unicode.items() if len(v) > 1),
        None,
    )
    if multi is not None:
        assert g.code_point_for_glyph_name(multi) is None


def test_code_point_for_glyph_name_synthesized_uni() -> None:
    g = GlyphList.DEFAULT
    # uniXXXX synthesized lookup also yields a single code point
    assert g.code_point_for_glyph_name("uni0041") == 0x41


# -- get_name (codepoint -> name reverse mapping) ---------------------------


def test_get_name_basic() -> None:
    g = GlyphList.DEFAULT
    assert g.get_name(0x41) == "A"
    assert g.get_name(0x00C1) == "Aacute"


def test_get_name_unknown_returns_none() -> None:
    assert GlyphList.DEFAULT.get_name(0xE000) is None


def test_get_name_invalid_returns_none() -> None:
    assert GlyphList.DEFAULT.get_name(-1) is None
    assert GlyphList.DEFAULT.get_name(0x110000) is None


# -- code_point_to_name_or_notdef (upstream parity) -------------------------


def test_code_point_to_name_or_notdef_known() -> None:
    g = GlyphList.DEFAULT
    assert g.code_point_to_name_or_notdef(0x41) == "A"
    assert g.code_point_to_name_or_notdef(0x00C1) == "Aacute"


def test_code_point_to_name_or_notdef_unknown() -> None:
    # Upstream returns ".notdef" rather than null when missing.
    assert GlyphList.DEFAULT.code_point_to_name_or_notdef(0xE000) == ".notdef"


# -- sequence_to_name (upstream parity) -------------------------------------


def test_sequence_to_name_single_codepoint() -> None:
    g = GlyphList.DEFAULT
    assert g.sequence_to_name("A") == "A"
    assert g.sequence_to_name("Á") == "Aacute"


def test_sequence_to_name_ligature() -> None:
    g = GlyphList.DEFAULT
    # The "fi" ligature maps to U+FB01 (a single code point), but multi-
    # codepoint entries should also reverse-resolve.
    assert g.sequence_to_name("ﬁ") == "fi"


def test_sequence_to_name_unknown_returns_notdef() -> None:
    g = GlyphList.DEFAULT
    assert g.sequence_to_name("") == ".notdef"
    assert g.sequence_to_name("definitely_not_a_glyph_value") == ".notdef"


def test_sequence_to_name_none_returns_notdef() -> None:
    assert GlyphList.DEFAULT.sequence_to_name(None) == ".notdef"


# -- AGL round-trip ---------------------------------------------------------


def test_agl_round_trip_letter_names() -> None:
    g = GlyphList.DEFAULT
    for name in ("A", "B", "Z", "a", "z", "zero", "nine"):
        unicode = g.to_unicode(name)
        assert unicode is not None
        assert g.code_point_to_name(ord(unicode)) == name


def test_agl_round_trip_diacritics() -> None:
    g = GlyphList.DEFAULT
    for name in ("Aacute", "Egrave", "Otilde", "Udieresis"):
        unicode = g.to_unicode(name)
        assert unicode is not None and len(unicode) == 1
        assert g.code_point_to_name(ord(unicode)) == name


# -- Zapf Dingbats round-trip ----------------------------------------------


def test_zapf_dingbats_round_trip() -> None:
    g = GlyphList.ZAPF_DINGBATS
    # zapfdingbats.txt: a1 -> 2701, a2 -> 2702, etc.
    for name in ("a1", "a2", "a202", "space"):
        unicode = g.to_unicode(name)
        assert unicode is not None
        # Reverse map: code_point_to_name should return the same glyph.
        cp = ord(unicode)
        recovered = g.code_point_to_name(cp)
        assert recovered == name


def test_zapf_dingbats_unicode_for_name_alias() -> None:
    g = GlyphList.ZAPF_DINGBATS
    assert g.unicode_for_name("a1") == g.to_unicode("a1")


def test_zapf_dingbats_code_point_for_glyph_name() -> None:
    g = GlyphList.ZAPF_DINGBATS
    # Spot-check upstream zapfdingbats.txt rows:
    # a1;2701, a2;2702, a202;2703
    assert g.code_point_for_glyph_name("a1") == 0x2701
    assert g.code_point_for_glyph_name("a2") == 0x2702
    assert g.code_point_for_glyph_name("a202") == 0x2703


def test_zapf_dingbats_get_name_reverse() -> None:
    g = GlyphList.ZAPF_DINGBATS
    assert g.get_name(0x2701) == "a1"
    assert g.get_name(0x2702) == "a2"
