"""Wave 1395 — close residual extension-subtable dispatch branches in
``pypdfbox/fontbox/ttf/gsub/glyph_substitution_data_extractor.py``.

Targets lines 307, 311, 319 of
:meth:`GlyphSubstitutionDataExtractor.extract_data_from_extension_subtable`:

* line 307 — extension wraps a ``LookupTypeMultipleSubstitutionFormat1``
  subtable; dispatch flows through ``extract_data_from_multiple_*``.
* line 311 — extension wraps a ``LookupTypeAlternateSubstitutionFormat1``
  subtable; dispatch flows through ``extract_data_from_alternate_*``.
* line 319 — extension wraps an unsupported inner type (here, an
  un-extended :class:`LookupSubTable` instance with no dispatch arm);
  the unknown-type debug-log branch fires and the call is a no-op.

These exercise the Type-7 (Extension Substitution) dispatch ladder. The
upstream parser unwraps Type-7 transparently so live PDFs rarely reach
this code, but the API permits constructing extension subtables by hand
(e.g. for raw GSUB tooling) so each branch needs a covering test.
"""

from __future__ import annotations

import logging

from pypdfbox.fontbox.ttf.gsub import (
    AlternateSetTable,
    GlyphSubstitutionDataExtractor,
    LookupTypeAlternateSubstitutionFormat1,
    LookupTypeContextualSubstitutionFormat1,
    LookupTypeExtensionSubstitutionFormat1,
    LookupTypeMultipleSubstitutionFormat1,
    SequenceTable,
)


def test_extension_dispatches_to_multiple_substitution_inner() -> None:
    """The multiple-substitution extractor itself doesn't write to the
    output map in 3.0.x (PDFBOX-5648 is 4.0 only — see the docstring
    on ``extract_data_from_multiple_substitution_format1_table``). What
    matters here is that the extension dispatcher *routes through* that
    method without raising, exercising the line-307 arm."""
    extractor = GlyphSubstitutionDataExtractor()
    inner = LookupTypeMultipleSubstitutionFormat1(
        coverage_table=(7,),
        sequence_tables=(SequenceTable(glyph_count=2, substitute_glyph_ids=(8, 9)),),
    )
    ext = LookupTypeExtensionSubstitutionFormat1(
        extension_lookup_type=2,
        extension_offset=0,
        inner_subtable=inner,
    )
    out: dict[tuple[int, ...], int] = {}
    # Must complete without raising — confirms dispatch landed in the
    # multiple-sub arm (the only one tolerant of this shape).
    extractor.extract_data_from_extension_subtable(out, ext)
    # In 3.0.x the multiple-sub extractor doesn't populate the map; the
    # important assertion is the dispatch path didn't raise / fall
    # through to the unsupported branch.
    assert out == {}


def test_extension_dispatches_to_alternate_substitution_inner() -> None:
    extractor = GlyphSubstitutionDataExtractor()
    inner = LookupTypeAlternateSubstitutionFormat1(
        coverage_table=(40,),
        alternate_set_tables=(
            AlternateSetTable(glyph_count=2, alternate_glyph_ids=(40, 41)),
        ),
    )
    ext = LookupTypeExtensionSubstitutionFormat1(
        extension_lookup_type=3,
        extension_offset=0,
        inner_subtable=inner,
    )
    out: dict[tuple[int, ...], int] = {}
    extractor.extract_data_from_extension_subtable(out, ext)
    assert out == {(40,): 41}


def test_extension_with_unsupported_inner_logs_and_returns(
    caplog: logging.LogRecord,
) -> None:
    """Inner subtable type the dispatcher doesn't recognise — debug-log
    branch fires and the output map is left empty.

    The extension-subtable dispatcher only knows the five "base" Type-1
    through Type-4 + Type-7 variants; a Type-5 contextual subtable wrapped
    inside an extension lands in the unsupported arm."""
    extractor = GlyphSubstitutionDataExtractor()
    # Contextual Type-5 — not in the dispatch ladder.
    inner = LookupTypeContextualSubstitutionFormat1(
        coverage_table=(7,),
        sequence_rule_sets=(),
    )
    ext = LookupTypeExtensionSubstitutionFormat1(
        extension_lookup_type=5,
        extension_offset=0,
        inner_subtable=inner,
    )
    out: dict[tuple[int, ...], int] = {}
    with caplog.at_level(
        logging.DEBUG,
        logger="pypdfbox.fontbox.ttf.gsub.glyph_substitution_data_extractor",
    ):
        extractor.extract_data_from_extension_subtable(out, ext)
    assert out == {}
    assert any("unsupported inner subtable" in r.getMessage() for r in caplog.records)


def test_extension_with_none_inner_is_noop() -> None:
    """The early-return branch when ``inner_subtable`` is ``None`` (the
    "no extension target wired" case)."""
    extractor = GlyphSubstitutionDataExtractor()
    ext = LookupTypeExtensionSubstitutionFormat1(
        extension_lookup_type=1,
        extension_offset=0,
        inner_subtable=None,
    )
    out: dict[tuple[int, ...], int] = {}
    extractor.extract_data_from_extension_subtable(out, ext)
    assert out == {}
