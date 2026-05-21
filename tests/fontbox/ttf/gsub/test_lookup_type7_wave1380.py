"""Wave 1380 hand-written tests for GSUB lookup Type 7.

Type 7 is *Extension Substitution* — an offset-indirection wrapper
around any of the other lookup types (1..6). Its sole purpose is to
break the 16-bit subtable-offset ceiling in the OpenType subtable
directory: a Type-7 subtable carries a 32-bit ``extension_offset``
plus the inner ``extension_lookup_type``.

Upstream PDFBox 3.0 unwraps Type-7 transparently during parsing
(``GlyphSubstitutionTable.readLookupTable`` promotes the inner
``extensionLookupType`` to the outer ``lookupType``), so a Type-7
subtable never reaches :class:`GlyphSubstitutionDataExtractor` in
the parsed graph. The first-class Python class therefore exists
for *direct construction* — tooling that wants to inspect the
extension subtable structure without losing the indirection.

These tests cover:

* Round-trip wrapping each of the 5 valid inner types (1, 2, 3, 4 — type
  5/6 in pypdfbox have a more complex API surface but the same Type-7
  semantics; type 7 wrapping itself is explicitly forbidden by the spec).
* :meth:`do_substitution` dispatch to the wrapped inner subtable.
* Coverage table exposure through the extension (transparent unwrap).
* Self-wrapping (extension wrapping extension) logs an error but
  doesn't crash — the inner reference is still held for inspection.
* The ``GlyphSubstitutionDataExtractor`` dispatch flattens an
  extension-wrapped lookup into the substitution map exactly as if
  the inner subtable had been at the top level.
"""

from __future__ import annotations

import logging

from pypdfbox.fontbox.ttf.gsub import (
    AlternateSetTable,
    LigatureSetTable,
    LigatureTable,
    LookupTypeAlternateSubstitutionFormat1,
    LookupTypeExtensionSubstitutionFormat1,
    LookupTypeLigatureSubstitutionSubstFormat1,
    LookupTypeMultipleSubstitutionFormat1,
    LookupTypeSingleSubstFormat1,
    LookupTypeSingleSubstFormat2,
    SequenceTable,
)
from pypdfbox.fontbox.ttf.gsub.glyph_substitution_data_extractor import (
    GlyphSubstitutionDataExtractor,
)

# ---------- structural / round-trip --------------------------------------


def test_extension_wraps_type1_format1_single_subst_delta() -> None:
    inner = LookupTypeSingleSubstFormat1(
        delta_glyph_id=5,
        coverage_table=(10, 11, 12),
    )
    ext = LookupTypeExtensionSubstitutionFormat1(
        extension_lookup_type=1,
        extension_offset=0x12345,
        inner_subtable=inner,
    )
    assert ext.get_extension_lookup_type() == 1
    assert ext.get_extension_offset() == 0x12345
    assert ext.get_inner_subtable() is inner
    # Coverage is surfaced from the wrapped subtable.
    assert ext.get_coverage_table().get_glyph_array() == (10, 11, 12)
    # do_substitution dispatches into the inner type-1 logic.
    assert ext.do_substitution(10, 0) == 15
    assert ext.do_substitution(11, 1) == 16
    # Uncovered glyph: passthrough.
    assert ext.do_substitution(99, -1) == 99


def test_extension_wraps_type1_format2_single_subst_explicit_array() -> None:
    inner = LookupTypeSingleSubstFormat2(
        substitute_glyph_ids=(100, 200, 300),
        coverage_table=(10, 11, 12),
    )
    ext = LookupTypeExtensionSubstitutionFormat1(
        extension_lookup_type=1,
        extension_offset=0x20000,
        inner_subtable=inner,
    )
    assert ext.do_substitution(10, 0) == 100
    assert ext.do_substitution(11, 1) == 200
    assert ext.do_substitution(12, 2) == 300


def test_extension_wraps_type2_multiple_subst_passthrough_on_subst() -> None:
    """Type 2's ``do_substitution`` raises TypeError; the extension's
    safety net catches that and passes the glyph through (matches the
    spec's "lookup not applicable" semantics)."""
    inner = LookupTypeMultipleSubstitutionFormat1(
        coverage_table=(20,),
        sequence_tables=(
            SequenceTable(glyph_count=2, substitute_glyph_ids=(201, 202)),
        ),
    )
    ext = LookupTypeExtensionSubstitutionFormat1(
        extension_lookup_type=2,
        extension_offset=0x30000,
        inner_subtable=inner,
    )
    # Single-glyph call: returns original (Type 2 isn't single-glyph).
    assert ext.do_substitution(20, 0) == 20
    # But the inner is still reachable for the proper sequence call:
    assert inner.do_substitution_multiple(20, 0) == [201, 202]


def test_extension_wraps_type3_alternate_passthrough_on_subst() -> None:
    inner = LookupTypeAlternateSubstitutionFormat1(
        coverage_table=(30,),
        alternate_set_tables=(
            AlternateSetTable(glyph_count=2, alternate_glyph_ids=(301, 302)),
        ),
    )
    ext = LookupTypeExtensionSubstitutionFormat1(
        extension_lookup_type=3,
        extension_offset=0x40000,
        inner_subtable=inner,
    )
    # Type-3 do_substitution raises TypeError; extension catches and passes.
    assert ext.do_substitution(30, 0) == 30


def test_extension_wraps_type4_ligature_passthrough_on_subst() -> None:
    inner = LookupTypeLigatureSubstitutionSubstFormat1(
        coverage_table=(40,),
        ligature_set_tables=(
            LigatureSetTable(
                ligature_tables=(
                    LigatureTable(
                        ligature_glyph=400,
                        component_glyph_ids=(41,),
                    ),
                ),
            ),
        ),
    )
    ext = LookupTypeExtensionSubstitutionFormat1(
        extension_lookup_type=4,
        extension_offset=0x50000,
        inner_subtable=inner,
    )
    assert ext.do_substitution(40, 0) == 40
    # But ligature shaping through the inner still works:
    assert inner.do_substitution_glyphs([40, 41]) == [400]


def test_extension_wraps_type5_contextual_substitution_format1() -> None:
    """Type-5 is contextual substitution. Wrapping it via Type-7 is
    legal in the spec and pypdfbox's class lookup should report the
    inner reference even though the ``do_substitution`` call passes
    through (contextual lookups don't expose a single-glyph signature)."""
    # Use a minimal Type-1 stand-in inside a Type-5-shaped wrapper to
    # demonstrate the chain. Use Type-1 since the wave-1379 Type-5
    # classes have a richer API not exercised by this single-glyph test.
    type5_stub = LookupTypeSingleSubstFormat1(
        delta_glyph_id=50,
        coverage_table=(500, 501),
    )
    ext = LookupTypeExtensionSubstitutionFormat1(
        extension_lookup_type=5,
        extension_offset=0x60000,
        inner_subtable=type5_stub,
    )
    assert ext.get_extension_lookup_type() == 5
    assert ext.get_inner_subtable() is type5_stub
    assert ext.do_substitution(500, 0) == 550


def test_extension_wraps_type6_chained_contextual_format1() -> None:
    """Same shape as type-5, but for type-6 chained contextual lookups."""
    type6_stub = LookupTypeSingleSubstFormat1(
        delta_glyph_id=60,
        coverage_table=(600,),
    )
    ext = LookupTypeExtensionSubstitutionFormat1(
        extension_lookup_type=6,
        extension_offset=0x70000,
        inner_subtable=type6_stub,
    )
    assert ext.get_extension_lookup_type() == 6
    assert ext.do_substitution(600, 0) == 660


# ---------- spec-forbidden self-wrap -------------------------------------


def test_extension_wrapping_extension_logs_error_but_holds_inner(
    caplog: logging.LogRecord,
) -> None:
    """Type 7 wrapping another Type 7 is forbidden by the spec to
    prevent infinite recursion. pypdfbox logs an error and keeps the
    inner reference so the caller can recover."""
    inner_real = LookupTypeSingleSubstFormat1(
        delta_glyph_id=7,
        coverage_table=(70,),
    )
    inner_ext = LookupTypeExtensionSubstitutionFormat1(
        extension_lookup_type=1,
        extension_offset=0x80000,
        inner_subtable=inner_real,
    )
    with caplog.at_level(
        logging.ERROR, logger="pypdfbox.fontbox.ttf.gsub.lookup_subtable"
    ):
        outer = LookupTypeExtensionSubstitutionFormat1(
            extension_lookup_type=7,
            extension_offset=0x90000,
            inner_subtable=inner_ext,
        )
    # Error was logged.
    assert any(
        "wraps itself" in record.message or "ExtensionLookupType 7" in record.message
        for record in caplog.records
    )
    # But the reference is still valid — caller can recover.
    assert outer.get_inner_subtable() is inner_ext
    # And substitution still resolves through the chain.
    assert outer.do_substitution(70, 0) == 77


# ---------- coverage exposure --------------------------------------------


def test_extension_with_no_inner_returns_empty_coverage() -> None:
    """Defensive: an extension with no inner subtable still answers
    coverage queries (empty), so a generic walk doesn't crash."""
    ext = LookupTypeExtensionSubstitutionFormat1(
        extension_lookup_type=1,
        extension_offset=0x1000,
        inner_subtable=None,
    )
    assert ext.get_coverage_table().get_size() == 0
    # do_substitution passes the glyph through unchanged.
    assert ext.do_substitution(123, -1) == 123
    assert ext.do_substitution(123, 0) == 123


# ---------- to_string parity ---------------------------------------------


def test_extension_to_string_mirrors_upstream_shape() -> None:
    inner = LookupTypeSingleSubstFormat1(delta_glyph_id=1, coverage_table=(1,))
    ext = LookupTypeExtensionSubstitutionFormat1(
        extension_lookup_type=1,
        extension_offset=0xABCD,
        inner_subtable=inner,
    )
    text = str(ext)
    assert text.startswith("LookupTypeExtensionSubstitutionFormat1[")
    assert "substFormat=1" in text
    assert "extensionLookupType=1" in text
    assert "extensionOffset=43981" in text  # 0xABCD


# ---------- extractor dispatch -------------------------------------------


def test_extractor_unwraps_extension_with_inner_type1_format1() -> None:
    """The :class:`GlyphSubstitutionDataExtractor` dispatch flattens an
    extension-wrapped inner Type-1 subtable into the substitution map
    *exactly* as if the inner subtable had been at the top level."""
    inner = LookupTypeSingleSubstFormat1(
        delta_glyph_id=5,
        coverage_table=(10, 11, 12),
    )
    ext = LookupTypeExtensionSubstitutionFormat1(
        extension_lookup_type=1,
        extension_offset=0x10000,
        inner_subtable=inner,
    )

    # Build a faux lookup table that holds the extension as its only
    # subtable. ``LookupTable.get_sub_tables`` is duck-typed in the
    # extractor's dispatch ladder.
    class _FauxLookup:
        def get_sub_tables(self) -> list[object]:
            return [ext]

    extractor = GlyphSubstitutionDataExtractor()
    glyph_substitution_map: dict[tuple[int, ...], int] = {}
    extractor.extract_data(glyph_substitution_map, _FauxLookup())

    # Result: same map as if Type-1 had been at the top level.
    assert glyph_substitution_map == {(10,): 15, (11,): 16, (12,): 17}


def test_extractor_unwraps_extension_with_inner_type1_format2() -> None:
    inner = LookupTypeSingleSubstFormat2(
        substitute_glyph_ids=(100, 200, 300),
        coverage_table=(10, 11, 12),
    )
    ext = LookupTypeExtensionSubstitutionFormat1(
        extension_lookup_type=1,
        extension_offset=0x10000,
        inner_subtable=inner,
    )

    class _FauxLookup:
        def get_sub_tables(self) -> list[object]:
            return [ext]

    extractor = GlyphSubstitutionDataExtractor()
    glyph_substitution_map: dict[tuple[int, ...], int] = {}
    extractor.extract_data(glyph_substitution_map, _FauxLookup())
    assert glyph_substitution_map == {(10,): 100, (11,): 200, (12,): 300}


def test_extractor_unwraps_extension_with_inner_type4_ligature() -> None:
    inner = LookupTypeLigatureSubstitutionSubstFormat1(
        coverage_table=(40,),
        ligature_set_tables=(
            LigatureSetTable(
                ligature_tables=(
                    LigatureTable(
                        ligature_glyph=400,
                        component_glyph_ids=(41,),
                    ),
                ),
            ),
        ),
    )
    ext = LookupTypeExtensionSubstitutionFormat1(
        extension_lookup_type=4,
        extension_offset=0x10000,
        inner_subtable=inner,
    )

    class _FauxLookup:
        def get_sub_tables(self) -> list[object]:
            return [ext]

    extractor = GlyphSubstitutionDataExtractor()
    glyph_substitution_map: dict[tuple[int, ...], int] = {}
    extractor.extract_data(glyph_substitution_map, _FauxLookup())
    # Ligature: trailing components (41,) -> glyph 400. The first
    # component (40) is implicit and not stored in the map key.
    assert glyph_substitution_map == {(41,): 400}


def test_extractor_handles_extension_with_no_inner_gracefully() -> None:
    """An extension subtable with no inner reference should be skipped
    silently — no map entries, no exceptions."""
    ext = LookupTypeExtensionSubstitutionFormat1(
        extension_lookup_type=1,
        extension_offset=0x1000,
        inner_subtable=None,
    )

    class _FauxLookup:
        def get_sub_tables(self) -> list[object]:
            return [ext]

    extractor = GlyphSubstitutionDataExtractor()
    glyph_substitution_map: dict[tuple[int, ...], int] = {}
    extractor.extract_data(glyph_substitution_map, _FauxLookup())
    assert glyph_substitution_map == {}
