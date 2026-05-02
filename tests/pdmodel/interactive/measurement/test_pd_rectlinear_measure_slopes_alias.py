"""Parity tests for ``PDRectlinearMeasureDictionary`` correctly-spelled
``get_line_slopes`` / ``set_line_slopes`` aliases.

Upstream PDFBox spells the methods ``getLineSloaps`` / ``setLineSloaps``
(a long-standing typo of "Slopes"). The misspelled methods are preserved
verbatim for API parity, but pypdfbox additionally exposes the correctly-
spelled aliases for callers writing fresh code. This module verifies both
spellings round-trip through the same underlying ``/S`` slot.
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.pdmodel.interactive.measurement import (
    PDNumberFormatDictionary,
    PDRectlinearMeasureDictionary,
)

_S = COSName.get_pdf_name("S")


def test_get_line_slopes_alias_delegates_to_get_line_sloaps() -> None:
    rl = PDRectlinearMeasureDictionary()
    nf = PDNumberFormatDictionary()
    rl.set_line_sloaps([nf])

    fetched = rl.get_line_slopes()
    assert fetched is not None
    assert len(fetched) == 1
    assert fetched[0].get_cos_object() is nf.get_cos_object()


def test_set_line_slopes_alias_writes_same_slot() -> None:
    rl = PDRectlinearMeasureDictionary()
    nf = PDNumberFormatDictionary()
    rl.set_line_slopes([nf])

    via_canonical = rl.get_line_sloaps()
    via_alias = rl.get_line_slopes()
    assert via_canonical is not None
    assert via_alias is not None
    assert len(via_canonical) == 1
    assert len(via_alias) == 1
    assert via_canonical[0].get_cos_object() is nf.get_cos_object()
    assert via_alias[0].get_cos_object() is nf.get_cos_object()


def test_set_line_slopes_targets_S_key() -> None:
    rl = PDRectlinearMeasureDictionary()
    nf = PDNumberFormatDictionary()
    rl.set_line_slopes([nf])

    raw = rl.get_cos_object().get_dictionary_object(_S)
    assert isinstance(raw, COSArray)
    assert raw.size() == 1
    entry = raw.get(0)
    assert isinstance(entry, COSDictionary)
    assert entry is nf.get_cos_object()


def test_get_line_slopes_default_is_none() -> None:
    rl = PDRectlinearMeasureDictionary()
    assert rl.get_line_slopes() is None
    assert rl.get_line_sloaps() is None


def test_set_line_sloaps_then_get_line_slopes_round_trip() -> None:
    # Reverse direction: write via the typo'd spelling, read via the
    # corrected alias — they share one /S slot.
    rl = PDRectlinearMeasureDictionary()
    nf_a = PDNumberFormatDictionary()
    nf_b = PDNumberFormatDictionary()
    rl.set_line_sloaps([nf_a, nf_b])

    fetched = rl.get_line_slopes()
    assert fetched is not None
    assert len(fetched) == 2
    assert fetched[0].get_cos_object() is nf_a.get_cos_object()
    assert fetched[1].get_cos_object() is nf_b.get_cos_object()


def test_set_line_slopes_accepts_tuple() -> None:
    rl = PDRectlinearMeasureDictionary()
    nf = PDNumberFormatDictionary()
    # Mirror the typed signature — tuple input is accepted alongside list.
    rl.set_line_slopes((nf,))

    fetched = rl.get_line_slopes()
    assert fetched is not None
    assert len(fetched) == 1
    assert fetched[0].get_cos_object() is nf.get_cos_object()
