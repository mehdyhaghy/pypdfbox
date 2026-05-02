"""Hand-written tests for ``Encoding`` predicate / typed-accessor helpers.

Covers Wave 195 additions on the abstract base ``Encoding``:

* ``PREDEFINED_NAMES`` — class constant matching the four PDF-spec
  ``/Encoding`` names recognized by upstream ``Encoding.getInstance``.
* ``is_predefined()`` — predicate.
* ``size()`` / ``__len__`` — code count.
* ``get_codes_for_name(name)`` — full reverse map (not just the first
  code, unlike ``get_code``).
* ``get_glyph_names()`` — distinct glyph-name set.
"""

from __future__ import annotations

from pypdfbox.cos import COSName
from pypdfbox.pdmodel.font.encoding import (
    BuiltInEncoding,
    DictionaryEncoding,
    Encoding,
    MacExpertEncoding,
    MacRomanEncoding,
    StandardEncoding,
    SymbolEncoding,
    WinAnsiEncoding,
    ZapfDingbatsEncoding,
)

# ---------- PREDEFINED_NAMES constant -------------------------------------


def test_predefined_names_is_frozenset_of_four():
    assert isinstance(Encoding.PREDEFINED_NAMES, frozenset)
    expected = frozenset({
        "StandardEncoding",
        "WinAnsiEncoding",
        "MacRomanEncoding",
        "MacExpertEncoding",
    })
    assert expected == Encoding.PREDEFINED_NAMES


def test_predefined_names_does_not_include_symbol_or_zapf():
    # These are font-program built-ins, not PDF-spec /Encoding names.
    assert "SymbolEncoding" not in Encoding.PREDEFINED_NAMES
    assert "ZapfDingbatsEncoding" not in Encoding.PREDEFINED_NAMES


def test_predefined_names_immutable():
    # frozenset has no add() — confirms Java-style read-only constant.
    assert not hasattr(Encoding.PREDEFINED_NAMES, "add")


def test_predefined_names_aligns_with_cos_name_constants():
    # The four entries must match the COSName aliases used by upstream
    # Encoding.getInstance(COSName).
    assert COSName.STANDARD_ENCODING.name in Encoding.PREDEFINED_NAMES
    assert COSName.WIN_ANSI_ENCODING.name in Encoding.PREDEFINED_NAMES
    assert COSName.MAC_ROMAN_ENCODING.name in Encoding.PREDEFINED_NAMES
    assert COSName.MAC_EXPERT_ENCODING.name in Encoding.PREDEFINED_NAMES


# ---------- is_predefined predicate ---------------------------------------


def test_is_predefined_true_for_pdf_spec_singletons():
    assert StandardEncoding.INSTANCE.is_predefined() is True
    assert WinAnsiEncoding.INSTANCE.is_predefined() is True
    assert MacRomanEncoding.INSTANCE.is_predefined() is True
    assert MacExpertEncoding.INSTANCE.is_predefined() is True


def test_is_predefined_false_for_symbol_and_zapf():
    assert SymbolEncoding.INSTANCE.is_predefined() is False
    assert ZapfDingbatsEncoding.INSTANCE.is_predefined() is False


def test_is_predefined_false_for_dictionary_encoding():
    enc = DictionaryEncoding(base_encoding=COSName.get_pdf_name("WinAnsiEncoding"))
    # DictionaryEncoding.get_encoding_name() = "WinAnsiEncoding with differences"
    assert enc.is_predefined() is False


def test_is_predefined_false_for_dictionary_encoding_type3():
    enc = DictionaryEncoding()
    # Type 3: get_encoding_name() = "differences"
    assert enc.is_predefined() is False


def test_is_predefined_false_for_built_in_encoding():
    enc = BuiltInEncoding({0x41: "A"})
    assert enc.is_predefined() is False


# ---------- size / __len__ ------------------------------------------------


def test_size_matches_code_to_name_map_size():
    enc = WinAnsiEncoding.INSTANCE
    assert enc.size() == len(enc.get_code_to_name_map())


def test_len_matches_size():
    enc = WinAnsiEncoding.INSTANCE
    assert len(enc) == enc.size()


def test_size_winansi_is_224_after_bullet_fillin():
    # WinAnsi explicit table + bullet fill-in for codes 0o41..0xFF
    # should cover the full upper range — empirical count is 224.
    assert WinAnsiEncoding.INSTANCE.size() == 224


def test_size_built_in_matches_input_dict_size():
    enc = BuiltInEncoding({0x41: "A", 0x42: "B", 0x43: "C"})
    assert enc.size() == 3
    assert len(enc) == 3


def test_size_dictionary_encoding_type3_zero_until_differences_added():
    enc = DictionaryEncoding()
    assert enc.size() == 0
    assert len(enc) == 0


def test_size_dictionary_encoding_with_base_inherits_full_count():
    enc = DictionaryEncoding(base_encoding=COSName.get_pdf_name("WinAnsiEncoding"))
    assert enc.size() == WinAnsiEncoding.INSTANCE.size()


# ---------- get_codes_for_name --------------------------------------------


def test_get_codes_for_name_single_match_for_letter_a():
    # 'A' is unique in WinAnsi.
    assert WinAnsiEncoding.INSTANCE.get_codes_for_name("A") == [0x41]


def test_get_codes_for_name_returns_all_bullet_codes():
    # WinAnsi fills every otherwise-unused code in 0o41..0xFF with
    # 'bullet' — there must be more than one.
    bullets = WinAnsiEncoding.INSTANCE.get_codes_for_name("bullet")
    assert len(bullets) > 1
    # The canonical /bullet position is 0o225 (149) from the explicit table.
    assert 0o225 in bullets


def test_get_codes_for_name_sorted_ascending():
    bullets = WinAnsiEncoding.INSTANCE.get_codes_for_name("bullet")
    assert bullets == sorted(bullets)


def test_get_codes_for_name_unknown_returns_empty_list():
    assert WinAnsiEncoding.INSTANCE.get_codes_for_name("xyzzy-not-real") == []


def test_get_codes_for_name_first_matches_get_code():
    # get_code returns the first-added (Map.putIfAbsent) reverse mapping.
    enc = WinAnsiEncoding.INSTANCE
    codes = enc.get_codes_for_name("bullet")
    # The single-result reverse map is one of the bullet codes.
    assert enc.get_code("bullet") in codes


def test_get_codes_for_name_consistent_across_calls():
    enc = WinAnsiEncoding.INSTANCE
    a = enc.get_codes_for_name("bullet")
    b = enc.get_codes_for_name("bullet")
    assert a == b
    # Snapshot — mutating the result must not affect the encoding.
    a.clear()
    assert enc.get_codes_for_name("bullet")  # still populated


def test_get_codes_for_name_for_standard_encoding():
    # Standard Encoding has no duplicate-name codes — every name maps to
    # exactly one code.
    enc = StandardEncoding.INSTANCE
    for name in enc.get_glyph_names():
        codes = enc.get_codes_for_name(name)
        assert len(codes) == 1


def test_get_codes_for_name_after_overwrite_in_dictionary_encoding():
    # DictionaryEncoding can overwrite a code's name; ensure get_codes_for_name
    # tracks the new mapping and drops the old.
    enc = DictionaryEncoding(base_encoding=COSName.get_pdf_name("WinAnsiEncoding"))
    # 'A' starts mapped to 0x41 only.
    assert enc.get_codes_for_name("A") == [0x41]
    # Overwrite 0x41 -> 'Aacute' (overwrite, not add — this clears the
    # reverse mapping for 'A' at code 0x41).
    enc.overwrite(0x41, "Aacute")
    assert 0x41 not in enc.get_codes_for_name("A")


# ---------- get_glyph_names -----------------------------------------------


def test_get_glyph_names_returns_set():
    gn = WinAnsiEncoding.INSTANCE.get_glyph_names()
    assert isinstance(gn, set)


def test_get_glyph_names_contains_basic_letters():
    gn = StandardEncoding.INSTANCE.get_glyph_names()
    for ch in ("A", "Z", "a", "z", "space"):
        assert ch in gn


def test_get_glyph_names_winansi_contains_bullet():
    assert "bullet" in WinAnsiEncoding.INSTANCE.get_glyph_names()


def test_get_glyph_names_count_le_size_due_to_bullet_collisions():
    enc = WinAnsiEncoding.INSTANCE
    # WinAnsi has duplicate names (every fill-in is 'bullet'); the distinct
    # name set is therefore strictly smaller than the code count.
    assert len(enc.get_glyph_names()) < enc.size()


def test_get_glyph_names_count_equal_to_size_for_standard():
    # Standard has no duplicate names.
    enc = StandardEncoding.INSTANCE
    assert len(enc.get_glyph_names()) == enc.size()


def test_get_glyph_names_snapshot_is_independent():
    enc = WinAnsiEncoding.INSTANCE
    gn = enc.get_glyph_names()
    gn.add("INJECTED")
    # The encoding's internal state is unchanged.
    assert "INJECTED" not in enc.get_glyph_names()
    assert enc.get_code("INJECTED") is None


def test_get_glyph_names_for_built_in_encoding():
    enc = BuiltInEncoding({0x41: "A", 0x42: "B", 0x43: "B"})
    # Distinct names only — the duplicate 'B' collapses.
    assert enc.get_glyph_names() == {"A", "B"}


def test_get_glyph_names_zapf_dingbats_uses_a_prefixed_names():
    # Zapf Dingbats uses dingbat names like 'a1', 'a2', ... not Latin glyphs.
    gn = ZapfDingbatsEncoding.INSTANCE.get_glyph_names()
    assert "a1" in gn
    assert "exclam" not in gn


# ---------- cross-helper consistency --------------------------------------


def test_size_equals_distinct_codes_count():
    for enc in (
        StandardEncoding.INSTANCE,
        WinAnsiEncoding.INSTANCE,
        MacRomanEncoding.INSTANCE,
        MacExpertEncoding.INSTANCE,
        SymbolEncoding.INSTANCE,
        ZapfDingbatsEncoding.INSTANCE,
    ):
        assert enc.size() == len(set(enc.get_code_to_name_map().keys()))


def test_get_codes_for_name_total_equals_size_for_no_duplicate_encodings():
    # For encodings without duplicate names, summing get_codes_for_name
    # over the glyph name set must equal size().
    enc = StandardEncoding.INSTANCE
    total = sum(len(enc.get_codes_for_name(n)) for n in enc.get_glyph_names())
    assert total == enc.size()


def test_glyph_names_subset_of_name_to_code_map_keys():
    enc = WinAnsiEncoding.INSTANCE
    assert enc.get_glyph_names() <= set(enc.get_name_to_code_map().keys())
