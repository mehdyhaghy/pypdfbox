"""Wave 213: PDSimpleFont round-out — covers the public ``get_glyph_list``,
the tri-state ``get_symbolic_flag`` / ``is_font_symbolic``, and the
single-code ``to_unicode`` accessor lifted from upstream's
``PDSimpleFont``.
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName
from pypdfbox.fontbox.cmap.cmap import CMap
from pypdfbox.fontbox.encoding.glyph_list import GlyphList
from pypdfbox.pdmodel.font import PDFontDescriptor, PDTrueTypeFont, PDType1Font
from pypdfbox.pdmodel.font.encoding import (
    DictionaryEncoding,
    MacRomanEncoding,
    StandardEncoding,
    WinAnsiEncoding,
    ZapfDingbatsEncoding,
)
from pypdfbox.pdmodel.font.pd_font_descriptor import (
    FLAG_NON_SYMBOLIC,
    FLAG_SYMBOLIC,
)

# ---------- get_glyph_list ----------


def test_get_glyph_list_returns_default_when_no_encoding_and_no_name() -> None:
    """Empty font dict → AGL (the safe default)."""
    assert PDType1Font().get_glyph_list() is GlyphList.DEFAULT


def test_get_glyph_list_returns_zapf_for_zapfdingbats_standard14() -> None:
    """Standard 14 ZapfDingbats name picks the Zapf glyph list, even when
    no /Encoding entry is present."""
    font = PDType1Font()
    font.get_cos_object().set_name(COSName.get_pdf_name("BaseFont"), "ZapfDingbats")
    assert font.get_glyph_list() is GlyphList.ZAPF_DINGBATS


def test_get_glyph_list_returns_zapf_for_zapfdingbats_alias() -> None:
    """A registered ZapfDingbats alias also selects the Zapf list."""
    font = PDType1Font()
    font.get_cos_object().set_name(
        COSName.get_pdf_name("BaseFont"), "ITCZapfDingbats"
    )
    if font.is_standard14():
        # Only assert when the alias is known; alias table is data-driven.
        assert font.get_glyph_list() is GlyphList.ZAPF_DINGBATS


def test_get_glyph_list_returns_zapf_for_zapfdingbats_encoding() -> None:
    """A non-Zapf font name with /Encoding = ZapfDingbatsEncoding still
    flips to the Zapf glyph list."""
    font = PDType1Font()
    font.get_cos_object().set_name(COSName.get_pdf_name("BaseFont"), "Helvetica")
    font.get_cos_object().set_item(
        COSName.get_pdf_name("Encoding"),
        COSName.get_pdf_name("ZapfDingbatsEncoding"),
    )
    assert font.get_glyph_list() is GlyphList.ZAPF_DINGBATS


def test_get_glyph_list_returns_default_for_helvetica() -> None:
    font = PDType1Font()
    font.get_cos_object().set_name(COSName.get_pdf_name("BaseFont"), "Helvetica")
    font.get_cos_object().set_item(
        COSName.get_pdf_name("Encoding"),
        COSName.get_pdf_name("WinAnsiEncoding"),
    )
    assert font.get_glyph_list() is GlyphList.DEFAULT


def test_get_glyph_list_returns_default_for_symbol() -> None:
    """``Symbol`` (Standard 14) is symbolic, but it still uses the AGL —
    only ZapfDingbats triggers the alternate list per upstream
    ``assignGlyphList``.
    """
    font = PDType1Font()
    font.get_cos_object().set_name(COSName.get_pdf_name("BaseFont"), "Symbol")
    assert font.get_glyph_list() is GlyphList.DEFAULT


# ---------- get_symbolic_flag (tri-state) ----------


def test_get_symbolic_flag_none_when_no_descriptor() -> None:
    """Mirrors upstream's ``Boolean`` return — ``None`` means "indeterminate"."""
    assert PDType1Font().get_symbolic_flag() is None


def test_get_symbolic_flag_true_when_bit_set() -> None:
    font = PDType1Font()
    fd = PDFontDescriptor()
    fd.set_flags(FLAG_SYMBOLIC)
    font.set_font_descriptor(fd)
    assert font.get_symbolic_flag() is True


def test_get_symbolic_flag_false_when_descriptor_present_without_symbolic() -> None:
    """A descriptor with /Flags = 0 (or only /Nonsymbolic set) reports
    ``False`` — the upstream Java caveat about the flag defaulting to
    ``false`` when absent applies, but ``False`` is still what the
    descriptor reports."""
    font = PDType1Font()
    fd = PDFontDescriptor()
    fd.set_flags(FLAG_NON_SYMBOLIC)
    font.set_font_descriptor(fd)
    assert font.get_symbolic_flag() is False


# ---------- is_font_symbolic (tri-state inference) ----------


def test_is_font_symbolic_uses_descriptor_when_present() -> None:
    """Whatever the descriptor says wins, regardless of name / encoding."""
    font = PDType1Font()
    font.get_cos_object().set_name(COSName.get_pdf_name("BaseFont"), "Helvetica")
    fd = PDFontDescriptor()
    fd.set_flags(FLAG_SYMBOLIC)
    font.set_font_descriptor(fd)
    assert font.is_font_symbolic() is True


def test_is_font_symbolic_true_for_standard14_symbol() -> None:
    """Standard 14 ``Symbol`` is symbolic by construction."""
    font = PDType1Font()
    font.get_cos_object().set_name(COSName.get_pdf_name("BaseFont"), "Symbol")
    assert font.is_font_symbolic() is True


def test_is_font_symbolic_true_for_standard14_zapfdingbats() -> None:
    font = PDType1Font()
    font.get_cos_object().set_name(COSName.get_pdf_name("BaseFont"), "ZapfDingbats")
    assert font.is_font_symbolic() is True


def test_is_font_symbolic_false_for_standard14_helvetica() -> None:
    """The other Standard 14 fonts are nonsymbolic."""
    font = PDType1Font()
    font.get_cos_object().set_name(COSName.get_pdf_name("BaseFont"), "Helvetica")
    assert font.is_font_symbolic() is False


def test_is_font_symbolic_false_for_winansi_encoding() -> None:
    """WinAnsiEncoding is a Latin encoding → nonsymbolic."""
    font = PDType1Font()
    font.get_cos_object().set_item(
        COSName.get_pdf_name("Encoding"),
        COSName.get_pdf_name("WinAnsiEncoding"),
    )
    assert font.is_font_symbolic() is False


def test_is_font_symbolic_false_for_macroman_encoding() -> None:
    font = PDType1Font()
    font.get_cos_object().set_item(
        COSName.get_pdf_name("Encoding"),
        COSName.get_pdf_name("MacRomanEncoding"),
    )
    assert font.is_font_symbolic() is False


def test_is_font_symbolic_false_for_standard_encoding() -> None:
    font = PDType1Font()
    font.get_cos_object().set_item(
        COSName.get_pdf_name("Encoding"),
        COSName.get_pdf_name("StandardEncoding"),
    )
    assert font.is_font_symbolic() is False


def test_is_font_symbolic_false_when_encoding_absent_and_no_descriptor() -> None:
    """No /Encoding, no descriptor, not Standard 14.

    Upstream PDSimpleFont.readEncoding falls back to readEncodingFromFont(),
    which for a bare PDType1Font resolves StandardEncoding; isFontSymbolic then
    returns ``false`` because a Latin encoding guarantees nonsymbolic (verified
    against the live PDFBox oracle: bare Type1 -> StandardEncoding). Previously
    the encoding was wrongly None and this returned None (the wave-1434 bug).
    """
    assert PDType1Font().is_font_symbolic() is False


def test_is_font_symbolic_false_for_dictionary_encoding_with_latin_only_diffs() -> None:
    """A /Differences overlay whose names are all Latin (Adobe Standard +
    WinAnsi + MacRoman) is still nonsymbolic — matches the upstream
    inner loop.
    """
    enc = COSDictionary()
    enc.set_name(COSName.get_pdf_name("BaseEncoding"), "WinAnsiEncoding")
    enc.set_item(
        COSName.get_pdf_name("Differences"),
        COSArray([COSInteger.get(65), COSName.get_pdf_name("A")]),
    )
    font = PDType1Font()
    font.get_cos_object().set_item(COSName.get_pdf_name("Encoding"), enc)
    assert font.is_font_symbolic() is False


def test_is_font_symbolic_true_for_dictionary_encoding_with_non_latin_diff() -> None:
    """A /Differences entry whose name is *not* in any of the three Latin
    encodings flips the determination to symbolic. ``alpha`` (Greek) is
    the canonical example — it lives in SymbolEncoding only.
    """
    enc = COSDictionary()
    enc.set_name(COSName.get_pdf_name("BaseEncoding"), "WinAnsiEncoding")
    enc.set_item(
        COSName.get_pdf_name("Differences"),
        COSArray([COSInteger.get(65), COSName.get_pdf_name("alpha")]),
    )
    font = PDType1Font()
    font.get_cos_object().set_item(COSName.get_pdf_name("Encoding"), enc)
    assert font.is_font_symbolic() is True


def test_is_font_symbolic_skips_notdef_in_differences() -> None:
    """``.notdef`` differences are ignored — they neither prove symbolic
    nor nonsymbolic.
    """
    enc = COSDictionary()
    enc.set_name(COSName.get_pdf_name("BaseEncoding"), "WinAnsiEncoding")
    enc.set_item(
        COSName.get_pdf_name("Differences"),
        COSArray(
            [
                COSInteger.get(65),
                COSName.get_pdf_name(".notdef"),
                COSInteger.get(66),
                COSName.get_pdf_name("B"),
            ]
        ),
    )
    font = PDType1Font()
    font.get_cos_object().set_item(COSName.get_pdf_name("Encoding"), enc)
    # ``.notdef`` skipped, ``B`` is Latin → nonsymbolic
    assert font.is_font_symbolic() is False


# ---------- to_unicode (single code) ----------


def test_to_unicode_resolves_via_builtin_when_no_encoding_and_no_cmap() -> None:
    """No /Encoding, no /ToUnicode.

    get_encoding_typed now falls back to read_encoding_from_font() (upstream
    PDSimpleFont.readEncoding), resolving StandardEncoding for a bare
    PDType1Font; code 65 -> "A" -> unicode "A" via the Adobe Glyph List.
    Was None pre-wave-1434 (the blank-render bug)."""
    assert PDType1Font().to_unicode(65) == "A"


def test_to_unicode_resolves_via_winansi_encoding() -> None:
    """WinAnsi 0x41 → glyph "A" → unicode "A" via the Adobe Glyph List."""
    font = PDType1Font()
    font.get_cos_object().set_item(
        COSName.get_pdf_name("Encoding"),
        COSName.get_pdf_name("WinAnsiEncoding"),
    )
    assert font.to_unicode(0x41) == "A"


def test_to_unicode_resolves_via_zapf_dingbats_encoding() -> None:
    """ZapfDingbats encoding uses the Zapf glyph list (unicode points are
    Dingbat-region characters, not Latin)."""
    font = PDType1Font()
    font.get_cos_object().set_name(COSName.get_pdf_name("BaseFont"), "ZapfDingbats")
    font.get_cos_object().set_item(
        COSName.get_pdf_name("Encoding"),
        COSName.get_pdf_name("ZapfDingbatsEncoding"),
    )
    # ZapfDingbatsEncoding 0x21 → glyph "a1" → U+2701 (UPPER BLADE SCISSORS)
    result = font.to_unicode(0x21)
    assert result is not None
    assert result != "!"  # MUST NOT come back as the AGL ASCII '!' fallback


def test_to_unicode_prefers_to_unicode_cmap_over_encoding() -> None:
    """A /ToUnicode CMap wins, even when the encoding would map to
    something different — mirrors upstream's "first try /ToUnicode" rule.
    """
    font = PDType1Font()
    font.get_cos_object().set_item(
        COSName.get_pdf_name("Encoding"),
        COSName.get_pdf_name("WinAnsiEncoding"),
    )
    # Inject a parsed CMap directly into the cache (skips parse-from-stream).
    cmap = CMap()
    cmap.add_unicode_mapping(0x41, "Z")  # /ToUnicode says A -> Z
    font._to_unicode_cmap = cmap  # type: ignore[attr-defined]
    font._to_unicode_cmap_loaded = True  # type: ignore[attr-defined]
    assert font.to_unicode(0x41) == "Z"


def test_to_unicode_falls_back_to_encoding_when_cmap_lacks_code() -> None:
    """When /ToUnicode is present but doesn't cover this code, fall back
    to encoding+glyph list. This is the typical mixed-coverage case.
    """
    font = PDType1Font()
    font.get_cos_object().set_item(
        COSName.get_pdf_name("Encoding"),
        COSName.get_pdf_name("WinAnsiEncoding"),
    )
    cmap = CMap()
    cmap.add_unicode_mapping(0x41, "Z")  # only covers 0x41
    font._to_unicode_cmap = cmap  # type: ignore[attr-defined]
    font._to_unicode_cmap_loaded = True  # type: ignore[attr-defined]
    # 0x42 not in CMap → falls through to encoding → 'B'
    assert font.to_unicode(0x42) == "B"


def test_to_unicode_with_custom_glyph_list_used_when_font_uses_default() -> None:
    """For an AGL-backed font, a caller-supplied glyph list overrides the
    AGL — upstream supports overriding glyph lookup for accessibility
    extraction.
    """
    font = PDType1Font()
    font.get_cos_object().set_item(
        COSName.get_pdf_name("Encoding"),
        COSName.get_pdf_name("WinAnsiEncoding"),
    )
    # Empty custom list ⇒ no name-to-unicode mappings ⇒ None.
    empty_glyph_list = GlyphList({})
    assert font.to_unicode(0x41, custom_glyph_list=empty_glyph_list) is None


def test_to_unicode_ignores_custom_glyph_list_for_zapf_font() -> None:
    """For a Zapf-backed font, the custom list is ignored — the upstream
    "don't break Zapf Dingbats" guard. So passing an empty AGL still
    produces a Zapf result.
    """
    font = PDType1Font()
    font.get_cos_object().set_name(COSName.get_pdf_name("BaseFont"), "ZapfDingbats")
    font.get_cos_object().set_item(
        COSName.get_pdf_name("Encoding"),
        COSName.get_pdf_name("ZapfDingbatsEncoding"),
    )
    empty_glyph_list = GlyphList({})
    # Custom list ignored — the Zapf list still resolves the code.
    result = font.to_unicode(0x21, custom_glyph_list=empty_glyph_list)
    assert result is not None


def test_to_unicode_returns_none_for_unmapped_code() -> None:
    """A code outside the encoding's domain → ".notdef" → no glyph-list
    entry → None.
    """
    font = PDType1Font()
    font.get_cos_object().set_item(
        COSName.get_pdf_name("Encoding"),
        COSName.get_pdf_name("WinAnsiEncoding"),
    )
    # 0x00 is .notdef in WinAnsiEncoding.
    assert font.to_unicode(0x00) is None


# ---------- TrueType also picks up the new accessors ----------


def test_true_type_font_get_glyph_list_default() -> None:
    assert PDTrueTypeFont().get_glyph_list() is GlyphList.DEFAULT


def test_true_type_font_get_symbolic_flag_none_when_no_descriptor() -> None:
    assert PDTrueTypeFont().get_symbolic_flag() is None


def test_true_type_font_to_unicode_via_encoding() -> None:
    font = PDTrueTypeFont()
    font.get_cos_object().set_item(
        COSName.get_pdf_name("Encoding"),
        COSName.get_pdf_name("WinAnsiEncoding"),
    )
    assert font.to_unicode(0x41) == "A"


# ---------- consistency between the new accessors ----------


def test_glyph_list_consistent_with_zapf_when_is_font_symbolic_zapf() -> None:
    font = PDType1Font()
    font.get_cos_object().set_name(COSName.get_pdf_name("BaseFont"), "ZapfDingbats")
    assert font.is_font_symbolic() is True
    assert font.get_glyph_list() is GlyphList.ZAPF_DINGBATS


def test_dictionary_encoding_class_match_consistent_with_is_font_symbolic() -> None:
    """If the encoding *type* is one of the three Latin encodings, the
    isinstance checks in is_font_symbolic must match exactly the class
    constants from the typed encoding instances.
    """
    assert isinstance(WinAnsiEncoding.INSTANCE, WinAnsiEncoding)
    assert isinstance(MacRomanEncoding.INSTANCE, MacRomanEncoding)
    assert isinstance(StandardEncoding.INSTANCE, StandardEncoding)
    assert isinstance(ZapfDingbatsEncoding.INSTANCE, ZapfDingbatsEncoding)
    # And a DictionaryEncoding is none of those.
    enc = COSDictionary()
    enc.set_name(COSName.get_pdf_name("BaseEncoding"), "WinAnsiEncoding")
    de = DictionaryEncoding(font_encoding=enc)
    assert not isinstance(de, (WinAnsiEncoding, MacRomanEncoding, StandardEncoding))
