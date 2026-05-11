"""Wave 1281: XrefTrailerObj data class port."""

from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSObjectKey
from pypdfbox.pdfparser import XrefTrailerObj, XrefType


def test_default_state() -> None:
    obj = XrefTrailerObj()
    assert obj.trailer is None
    assert obj.xref_type is XrefType.TABLE
    assert obj.xref_table == {}


def test_reset_clears_entries() -> None:
    obj = XrefTrailerObj()
    obj.xref_table[COSObjectKey(1, 0)] = 100
    obj.reset()
    assert obj.xref_table == {}


def test_can_carry_trailer_dict() -> None:
    obj = XrefTrailerObj()
    trailer = COSDictionary()
    obj.trailer = trailer
    assert obj.trailer is trailer
