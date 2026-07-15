"""Regression tests for the per-code ``to_unicode`` / ``get_width`` memo and
the ``get_glyph_list`` derived-value memo added as pure performance fixes.

Each memo must be *behaviour-transparent*: the cached answer for every code
must equal the answer a fresh, un-warmed font produces, ``None`` results must
be cached (not recomputed as misses), and the ``custom_glyph_list`` override
must never be served from — nor pollute — the default-path cache.
"""
from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName
from pypdfbox.fontbox.encoding.glyph_list import GlyphList
from pypdfbox.pdmodel.font import PDType1Font


def _helvetica() -> PDType1Font:
    d = COSDictionary()
    d.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("Font"))
    d.set_item(COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Type1"))
    d.set_item(COSName.get_pdf_name("BaseFont"), COSName.get_pdf_name("Helvetica"))
    return PDType1Font(d)


def _zapf() -> PDType1Font:
    d = COSDictionary()
    d.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("Font"))
    d.set_item(COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Type1"))
    d.set_item(COSName.get_pdf_name("BaseFont"), COSName.get_pdf_name("ZapfDingbats"))
    return PDType1Font(d)


# ---------- Fix 1: get_glyph_list derived-value memo ----------


def test_get_glyph_list_is_stable_and_matches_fresh_font() -> None:
    warm = _helvetica()
    first = warm.get_glyph_list()
    # Call many times — every call must return the identical singleton.
    for _ in range(5):
        assert warm.get_glyph_list() is first
    assert first is GlyphList.DEFAULT
    # A pristine font (never warmed) resolves to the same value.
    assert _helvetica().get_glyph_list() is first


def test_get_glyph_list_zapf_derives_zapf_and_memoizes() -> None:
    font = _zapf()
    assert font.get_glyph_list() is GlyphList.ZAPF_DINGBATS
    # memo populated in the dedicated field, not in ``_glyph_list``
    assert font._derived_glyph_list is GlyphList.ZAPF_DINGBATS
    assert font._glyph_list is None
    assert font.get_glyph_list() is GlyphList.ZAPF_DINGBATS


def test_explicit_assign_glyph_list_still_wins_over_derived_memo() -> None:
    font = _helvetica()
    # Derive + memo the default first.
    assert font.get_glyph_list() is GlyphList.DEFAULT
    # An explicit assignment must take precedence on the next call.
    font.assign_glyph_list("ZapfDingbats")
    assert font._glyph_list is GlyphList.ZAPF_DINGBATS
    assert font.get_glyph_list() is GlyphList.ZAPF_DINGBATS


def test_derived_memo_does_not_leak_between_instances() -> None:
    a = _zapf()
    b = _helvetica()
    assert a.get_glyph_list() is GlyphList.ZAPF_DINGBATS
    assert b.get_glyph_list() is GlyphList.DEFAULT


# ---------- Fix 2: per-code to_unicode memo ----------


def test_to_unicode_cached_equals_uncached_for_every_code() -> None:
    warm = _helvetica()
    for code in range(256):
        # Fresh font per code = never-cached reference answer.
        ref = _helvetica().to_unicode(code)
        got1 = warm.to_unicode(code)  # populates cache
        got2 = warm.to_unicode(code)  # served from cache
        assert got1 == ref
        assert got2 == ref
        assert code in warm._code_to_unicode


def test_to_unicode_caches_none_results() -> None:
    font = _helvetica()
    # Code 0 maps to .notdef -> no unicode -> None.
    assert font.to_unicode(0) is None
    assert 0 in font._code_to_unicode
    assert font._code_to_unicode[0] is None
    # A second call still returns None (cache membership, not truthiness).
    assert font.to_unicode(0) is None


def test_custom_glyph_list_bypasses_and_does_not_pollute_default_cache() -> None:
    font = _helvetica()
    reference = _helvetica()
    # Prime the default cache for code 65.
    default_val = font.to_unicode(65)
    assert default_val == reference.to_unicode(65)
    # A custom glyph list call must NOT be served from the default cache and
    # must NOT overwrite it.
    custom = GlyphList.ZAPF_DINGBATS
    custom_val = font.to_unicode(65, custom)
    assert custom_val == _helvetica().to_unicode(65, custom)
    # Default cache entry unchanged.
    assert font._code_to_unicode[65] == default_val
    assert font.to_unicode(65) == default_val


def test_custom_glyph_list_first_does_not_seed_default_cache() -> None:
    font = _helvetica()
    custom = GlyphList.ZAPF_DINGBATS
    # Call the custom path first — must not create a default cache entry.
    font.to_unicode(66, custom)
    assert 66 not in font._code_to_unicode
    # The subsequent default call still yields the correct (default) answer.
    assert font.to_unicode(66) == _helvetica().to_unicode(66)


def test_to_unicode_with_to_unicode_cmap_is_cached_and_correct() -> None:
    # Build a /ToUnicode stream mapping code 0x41 -> 'Z' so the CMap path
    # (not the encoding path) drives the result, and confirm caching.
    from pypdfbox.cos import COSStream

    cmap_text = (
        b"/CIDInit /ProcSet findresource begin 12 dict begin begincmap\n"
        b"1 begincodespacerange <00> <ff> endcodespacerange\n"
        b"1 beginbfchar <41> <005A> endbfchar\n"
        b"endcmap CMapName currentdict /CMap defineresource pop end end\n"
    )
    stream = COSStream()
    stream.set_data(cmap_text)
    font = _helvetica()
    font.get_cos_object().set_item(COSName.get_pdf_name("ToUnicode"), stream)
    assert font.to_unicode(0x41) == "Z"  # CMap wins
    assert font._code_to_unicode[0x41] == "Z"
    assert font.to_unicode(0x41) == "Z"


# ---------- widths untouched ----------


def test_widths_unchanged_by_memo_work() -> None:
    d = COSDictionary()
    d.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("Font"))
    d.set_item(COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Type1"))
    d.set_item(COSName.get_pdf_name("BaseFont"), COSName.get_pdf_name("Helvetica"))
    d.set_int(COSName.get_pdf_name("FirstChar"), 65)
    d.set_int(COSName.get_pdf_name("LastChar"), 66)
    d.set_item(
        COSName.get_pdf_name("Widths"),
        COSArray([COSInteger.get(600), COSInteger.get(700)]),
    )
    font = PDType1Font(d)
    assert font.get_width(65) == 600.0
    assert font.get_width(65) == 600.0  # cached
    assert font.get_width(66) == 700.0
