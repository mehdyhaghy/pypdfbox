"""Hand-written tests for the Wave 261 ``Encoding`` helpers.

Covers the small additive surface added on top of Wave 195's predicate
helpers:

* ``FONT_SPECIFIC_NAMES`` constant — the names of font-program built-in
  encodings (Symbol, ZapfDingbats).
* ``is_font_specific()`` — predicate dual to ``is_predefined()``.
* ``get_max_code()`` / ``get_min_code()`` — code range introspection,
  with ``None`` for empty encodings.
* ``iter_codes()`` — sorted-code iterator.
* ``MacOSRomanEncoding.DIFFERENCES`` — public read-only view of the
  16 vendor-specific Mac OS Roman differences.
"""

from __future__ import annotations

from types import MappingProxyType

import pytest

from pypdfbox.cos import COSName
from pypdfbox.pdmodel.font.encoding import (
    BuiltInEncoding,
    DictionaryEncoding,
    Encoding,
    MacExpertEncoding,
    MacOSRomanEncoding,
    MacRomanEncoding,
    StandardEncoding,
    SymbolEncoding,
    WinAnsiEncoding,
    ZapfDingbatsEncoding,
)

# ---------- FONT_SPECIFIC_NAMES constant ----------------------------------


def test_font_specific_names_is_frozenset_of_two():
    assert isinstance(Encoding.FONT_SPECIFIC_NAMES, frozenset)
    assert frozenset(
        {"SymbolEncoding", "ZapfDingbatsEncoding"}
    ) == Encoding.FONT_SPECIFIC_NAMES


def test_font_specific_names_immutable():
    # frozenset has no add() method.
    assert not hasattr(Encoding.FONT_SPECIFIC_NAMES, "add")


def test_font_specific_names_disjoint_from_predefined_names():
    # No encoding can be both PDF-spec predefined and a font-program
    # built-in — they are categorically distinct.
    assert (
        Encoding.FONT_SPECIFIC_NAMES.isdisjoint(Encoding.PREDEFINED_NAMES)
    )


# ---------- is_font_specific predicate ------------------------------------


def test_is_font_specific_true_for_symbol_and_zapf():
    assert SymbolEncoding.INSTANCE.is_font_specific() is True
    assert ZapfDingbatsEncoding.INSTANCE.is_font_specific() is True


def test_is_font_specific_false_for_pdf_spec_singletons():
    assert StandardEncoding.INSTANCE.is_font_specific() is False
    assert WinAnsiEncoding.INSTANCE.is_font_specific() is False
    assert MacRomanEncoding.INSTANCE.is_font_specific() is False
    assert MacExpertEncoding.INSTANCE.is_font_specific() is False


def test_is_font_specific_false_for_mac_os_roman():
    # Mac OS Roman is a vendor extension of MacRoman, not a font-program
    # built-in. Its encoding name remains "MacRomanEncoding" via inheritance.
    assert MacOSRomanEncoding.INSTANCE.is_font_specific() is False


def test_is_font_specific_false_for_dictionary_encoding():
    enc = DictionaryEncoding(base_encoding=COSName.get_pdf_name("WinAnsiEncoding"))
    assert enc.is_font_specific() is False


def test_is_font_specific_false_for_built_in_encoding():
    enc = BuiltInEncoding({0x41: "A"})
    assert enc.is_font_specific() is False


def test_predefined_and_font_specific_are_mutually_exclusive():
    # No encoding satisfies both predicates.
    for enc in (
        StandardEncoding.INSTANCE,
        WinAnsiEncoding.INSTANCE,
        MacRomanEncoding.INSTANCE,
        MacExpertEncoding.INSTANCE,
        SymbolEncoding.INSTANCE,
        ZapfDingbatsEncoding.INSTANCE,
        MacOSRomanEncoding.INSTANCE,
        BuiltInEncoding({0x41: "A"}),
        DictionaryEncoding(),
    ):
        assert not (enc.is_predefined() and enc.is_font_specific())


# ---------- get_max_code / get_min_code -----------------------------------


def test_get_max_code_winansi_is_0xff():
    # Bullet fill-in extends WinAnsi up to 0xFF.
    assert WinAnsiEncoding.INSTANCE.get_max_code() == 0xFF


def test_get_min_code_winansi_starts_at_explicit_first():
    # Lowest mapped code from the WinAnsi table.
    enc = WinAnsiEncoding.INSTANCE
    code = enc.get_min_code()
    # Must match the smallest key in the snapshot map.
    assert code == min(enc.get_code_to_name_map().keys())
    assert code is not None


def test_get_min_code_standard_starts_at_0x20():
    # Adobe Standard Encoding's first printable position is 'space' at 0x20.
    assert StandardEncoding.INSTANCE.get_min_code() == 0x20


def test_get_max_code_built_in_matches_input_max():
    enc = BuiltInEncoding({10: "x", 50: "y", 30: "z"})
    assert enc.get_max_code() == 50


def test_get_min_code_built_in_matches_input_min():
    enc = BuiltInEncoding({10: "x", 50: "y", 30: "z"})
    assert enc.get_min_code() == 10


def test_get_max_code_empty_encoding_returns_none():
    enc = BuiltInEncoding({})
    assert enc.get_max_code() is None


def test_get_min_code_empty_encoding_returns_none():
    enc = BuiltInEncoding({})
    assert enc.get_min_code() is None


def test_get_max_code_type3_dict_encoding_is_none():
    # Bare DictionaryEncoding (Type 3, no base, no differences) is empty.
    enc = DictionaryEncoding()
    assert enc.get_max_code() is None
    assert enc.get_min_code() is None


def test_get_max_code_dict_encoding_with_base_inherits_winansi_max():
    enc = DictionaryEncoding(base_encoding=COSName.get_pdf_name("WinAnsiEncoding"))
    assert enc.get_max_code() == 0xFF


def test_min_le_max_for_predefined_singletons():
    for enc in (
        StandardEncoding.INSTANCE,
        WinAnsiEncoding.INSTANCE,
        MacRomanEncoding.INSTANCE,
        MacExpertEncoding.INSTANCE,
        SymbolEncoding.INSTANCE,
        ZapfDingbatsEncoding.INSTANCE,
    ):
        lo = enc.get_min_code()
        hi = enc.get_max_code()
        assert lo is not None
        assert hi is not None
        assert lo <= hi


def test_max_code_within_byte_range_for_all_predefined():
    # All single-byte encodings stay inside the 0..255 window.
    for enc in (
        StandardEncoding.INSTANCE,
        WinAnsiEncoding.INSTANCE,
        MacRomanEncoding.INSTANCE,
        MacExpertEncoding.INSTANCE,
        SymbolEncoding.INSTANCE,
        ZapfDingbatsEncoding.INSTANCE,
        MacOSRomanEncoding.INSTANCE,
    ):
        assert 0 <= enc.get_min_code() <= 0xFF
        assert 0 <= enc.get_max_code() <= 0xFF


# ---------- iter_codes ----------------------------------------------------


def test_iter_codes_yields_sorted_codes():
    enc = BuiltInEncoding({30: "c", 10: "a", 50: "b", 20: "d"})
    assert list(enc.iter_codes()) == [10, 20, 30, 50]


def test_iter_codes_empty_for_empty_encoding():
    enc = BuiltInEncoding({})
    assert list(enc.iter_codes()) == []


def test_iter_codes_returns_iterator_not_list():
    # Must be lazy — confirm it's an iterator, not a materialized list.
    enc = BuiltInEncoding({1: "a"})
    result = enc.iter_codes()
    assert iter(result) is result  # iterator-of-itself property


def test_iter_codes_count_matches_size():
    enc = WinAnsiEncoding.INSTANCE
    assert sum(1 for _ in enc.iter_codes()) == enc.size()


def test_iter_codes_first_equals_get_min_code():
    enc = StandardEncoding.INSTANCE
    first = next(enc.iter_codes())
    assert first == enc.get_min_code()


def test_iter_codes_last_equals_get_max_code():
    enc = StandardEncoding.INSTANCE
    *_, last = enc.iter_codes()
    assert last == enc.get_max_code()


def test_iter_codes_independent_invocations():
    # Each call returns a fresh iterator.
    enc = BuiltInEncoding({1: "a", 2: "b"})
    a = list(enc.iter_codes())
    b = list(enc.iter_codes())
    assert a == b == [1, 2]


def test_iter_codes_for_dict_encoding_includes_base_and_diffs():
    from pypdfbox.cos import COSArray, COSInteger

    diffs = COSArray()
    diffs.add(COSInteger.get(0xF0))
    diffs.add(COSName.get_pdf_name("custom"))
    enc = DictionaryEncoding(
        base_encoding=COSName.get_pdf_name("WinAnsiEncoding"),
        differences=diffs,
    )
    codes = list(enc.iter_codes())
    # Includes WinAnsi's 0x41 ('A') and the diff at 0xF0.
    assert 0x41 in codes
    assert 0xF0 in codes
    # And remains sorted.
    assert codes == sorted(codes)


# ---------- MacOSRomanEncoding.DIFFERENCES --------------------------------


def test_mac_os_roman_differences_is_mapping_proxy():
    assert isinstance(MacOSRomanEncoding.DIFFERENCES, MappingProxyType)


def test_mac_os_roman_differences_contains_sixteen_entries():
    assert len(MacOSRomanEncoding.DIFFERENCES) == 16


def test_mac_os_roman_differences_includes_known_glyphs():
    diffs = MacOSRomanEncoding.DIFFERENCES
    assert diffs[0o333] == "Euro"
    assert diffs[0o360] == "apple"
    assert diffs[0o255] == "notequal"
    assert diffs[0o275] == "Omega"


def test_mac_os_roman_differences_immutable():
    # MappingProxyType raises TypeError on item assignment.
    with pytest.raises(TypeError):
        MacOSRomanEncoding.DIFFERENCES[0xFF] = "BOGUS"  # type: ignore[index]


def test_mac_os_roman_differences_glyphs_are_actually_in_encoding():
    enc = MacOSRomanEncoding.INSTANCE
    for code, name in MacOSRomanEncoding.DIFFERENCES.items():
        assert enc.get_name(code) == name


def test_mac_os_roman_differences_all_codes_in_byte_range():
    for code in MacOSRomanEncoding.DIFFERENCES:
        assert 0 <= code <= 0xFF


def test_mac_os_roman_differences_no_duplicate_codes():
    # The underlying tuple has 16 entries; converting to a dict view must
    # not collapse any of them (i.e. all codes are distinct).
    assert len(MacOSRomanEncoding.DIFFERENCES) == 16


def test_mac_os_roman_differences_overlay_changes_glyph():
    # Position 0o333 in plain MacRoman is not 'Euro' — the overlay changes
    # the glyph name. Verify the difference is real, not a no-op.
    plain = MacRomanEncoding.INSTANCE.get_name(0o333)
    assert plain != "Euro"
    # ...but Mac OS Roman maps it to Euro via the difference table.
    assert MacOSRomanEncoding.INSTANCE.get_name(0o333) == "Euro"


# ---------- cross-helper consistency --------------------------------------


def test_iter_codes_matches_sorted_code_to_name_map_keys():
    enc = WinAnsiEncoding.INSTANCE
    assert list(enc.iter_codes()) == sorted(enc.get_code_to_name_map().keys())


def test_max_code_equals_max_of_iter_codes():
    enc = StandardEncoding.INSTANCE
    assert enc.get_max_code() == max(enc.iter_codes())


def test_min_code_equals_min_of_iter_codes():
    enc = StandardEncoding.INSTANCE
    assert enc.get_min_code() == min(enc.iter_codes())
