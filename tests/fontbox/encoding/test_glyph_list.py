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
