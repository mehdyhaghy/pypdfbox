"""Upstream-parity tests for :class:`pypdfbox.fontbox.encoding.GlyphList`.

There is no ``GlyphListTest.java`` in upstream PDFBox 3.0.x — these tests
target the documented contract of
``org.apache.pdfbox.pdmodel.font.encoding.GlyphList`` (load/loadList/toUnicode/
codePointToName/sequenceToName) and exercise the parser to confirm bytewise
parity with the Adobe glyphlist format used upstream.
"""

from __future__ import annotations

import io

import pytest

from pypdfbox.fontbox.encoding import GlyphList

# -- toUnicode (upstream semantics) -----------------------------------------


def test_to_unicode_known_name() -> None:
    g = GlyphList.get_adobe_glyph_list()
    # GlyphList.java line 214: toUnicode("A") -> "A"
    assert g.to_unicode("A") == "A"


def test_to_unicode_unknown_returns_none() -> None:
    # GlyphList.java lines 216-219: null name -> null; missing -> null
    g = GlyphList.get_adobe_glyph_list()
    assert g.to_unicode(None) is None
    assert g.to_unicode("not_a_glyph_name") is None


def test_to_unicode_suffix_stripped() -> None:
    # GlyphList.java lines 232-234: "foo.bar" recurses on "foo".
    g = GlyphList.get_adobe_glyph_list()
    assert g.to_unicode("A.alt") == "A"


def test_to_unicode_uniXXXX_synthesized() -> None:
    # GlyphList.java lines 236-251: uniXXXX -> chr(int(XXXX, 16)).
    g = GlyphList.get_adobe_glyph_list()
    assert g.to_unicode("uni0041") == "A"
    assert g.to_unicode("u0041") == "A"


def test_to_unicode_surrogate_disallowed() -> None:
    # GlyphList.java lines 244-247: code points D800..DFFF rejected.
    g = GlyphList.get_adobe_glyph_list()
    assert g.to_unicode("uniD800") is None


def test_to_unicode_invalid_hex_returns_none() -> None:
    # GlyphList.java lines 252-256: NumberFormatException -> warn + null.
    g = GlyphList.get_adobe_glyph_list()
    assert g.to_unicode("uniZZZZ") is None


# -- codePointToName (upstream returns ".notdef" on miss) -------------------


def test_code_point_to_name_known() -> None:
    # GlyphList.java line 184-189: returns name or ".notdef".
    g = GlyphList.get_adobe_glyph_list()
    assert g.code_point_to_name_or_notdef(0x41) == "A"


def test_code_point_to_name_missing_returns_notdef() -> None:
    g = GlyphList.get_adobe_glyph_list()
    # PUA code point not in AGL.
    assert g.code_point_to_name_or_notdef(0xE000) == ".notdef"


# -- sequenceToName ---------------------------------------------------------


def test_sequence_to_name_known() -> None:
    # GlyphList.java line 198-206: returns name or ".notdef".
    g = GlyphList.get_adobe_glyph_list()
    assert g.sequence_to_name("A") == "A"


def test_sequence_to_name_unknown_returns_notdef() -> None:
    g = GlyphList.get_adobe_glyph_list()
    assert g.sequence_to_name("totally_unmapped") == ".notdef"


# -- load / load_list (upstream parser) -------------------------------------


_SAMPLE = b"""# comment line, must be skipped
A;0041
Aacute;00C1
fi;FB01
ffi;FB03
"""


def test_load_from_bytes() -> None:
    # Mirrors GlyphList.java line 100-105 ctor (InputStream + count).
    g = GlyphList.load(_SAMPLE, 4)
    assert g.to_unicode("A") == "A"
    assert g.to_unicode("Aacute") == "Á"
    assert g.to_unicode("fi") == "ﬁ"


def test_load_from_stream() -> None:
    g = GlyphList.load(io.BytesIO(_SAMPLE), 4)
    assert g.to_unicode("ffi") == "ﬃ"


def test_load_skips_comments_and_blank() -> None:
    # GlyphList.java line 128: lines beginning with '#' are skipped.
    g = GlyphList.load(b"# only a comment\n\nA;0041\n", 1)
    assert g.to_unicode("A") == "A"
    assert len(g._name_to_unicode) == 1


def test_load_invalid_entry_raises() -> None:
    # GlyphList.java line 131-134: parts.length < 2 -> IOException.
    with pytest.raises(OSError):
        GlyphList.load(b"badline_without_semicolon\n", 1)


def test_load_invalid_hex_raises() -> None:
    # GlyphList.java line 143: Integer.parseInt(hex, 16) -> NumberFormatException.
    # Upstream propagates as an unchecked exception; we surface OSError to
    # keep the parser's failure mode uniform.
    with pytest.raises(OSError):
        GlyphList.load(b"A;ZZZZ\n", 1)


def test_load_list_returns_dict() -> None:
    # Pythonic helper: parse to dict without constructing a GlyphList.
    mapping = GlyphList.load_list(_SAMPLE)
    assert mapping["A"] == "A"
    assert mapping["fi"] == "ﬁ"


def test_load_with_base_extends_existing() -> None:
    # Mirrors GlyphList.java line 114-119 ctor (GlyphList existing, InputStream).
    base = GlyphList.load(b"A;0041\n", 1)
    extended = GlyphList.load(b"B;0042\n", 1, base=base)
    assert extended.to_unicode("A") == "A"
    assert extended.to_unicode("B") == "B"
    # base must remain unchanged (instances are immutable post-construction).
    assert base.to_unicode("B") is None


def test_load_multi_codepoint_entry() -> None:
    # GlyphList.java line 137-145: supports space-separated hex sequences.
    g = GlyphList.load(b"foo;0041 0042\n", 1)
    assert g.to_unicode("foo") == "AB"


# -- factory parity ---------------------------------------------------------


def test_get_adobe_glyph_list_returns_singleton() -> None:
    # GlyphList.java line 71-74: getAdobeGlyphList() returns DEFAULT.
    assert GlyphList.get_adobe_glyph_list() is GlyphList.DEFAULT


def test_get_zapf_dingbats_returns_singleton() -> None:
    # GlyphList.java line 81-84: getZapfDingbats() returns ZAPF_DINGBATS.
    assert GlyphList.get_zapf_dingbats() is GlyphList.ZAPF_DINGBATS
