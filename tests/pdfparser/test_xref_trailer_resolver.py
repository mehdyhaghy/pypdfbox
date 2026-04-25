from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSInteger, COSObjectKey
from pypdfbox.pdfparser import XrefEntry, XrefTrailerResolver, XrefType


def _entry(offset: int) -> XrefEntry:
    return XrefEntry(type=XrefType.TABLE, offset=offset)


def test_empty_resolver() -> None:
    r = XrefTrailerResolver()
    assert r.section_count() == 0
    assert r.get_xref_table() == {}
    assert r.get_trailer() is None


def test_single_section_round_trip() -> None:
    r = XrefTrailerResolver()
    r.begin_section(1234)
    r.set_entry(COSObjectKey(1, 0), _entry(10))
    r.set_entry(COSObjectKey(2, 0), _entry(50))
    trailer = COSDictionary()
    trailer.set_int("Size", 3)
    r.set_trailer(trailer)
    table = r.get_xref_table()
    assert len(table) == 2
    assert table[COSObjectKey(1, 0)].offset == 10
    merged_trailer = r.get_trailer()
    assert merged_trailer is not None
    assert merged_trailer.get_int("Size") == 3


def test_multiple_sections_newer_overrides_older() -> None:
    r = XrefTrailerResolver()
    # Newer (parsed first via startxref)
    r.begin_section(2000)
    r.set_entry(COSObjectKey(1, 0), _entry(200))
    r.set_entry(COSObjectKey(2, 0), _entry(250))
    t1 = COSDictionary()
    t1.set_int("Size", 5)
    r.set_trailer(t1)
    # Older (reached via /Prev)
    r.begin_section(1000)
    r.set_entry(COSObjectKey(1, 0), _entry(10))  # superseded by newer
    r.set_entry(COSObjectKey(3, 0), _entry(80))  # only in older
    t2 = COSDictionary()
    t2.set_int("Size", 3)
    t2.set_int("Prev", 0)
    r.set_trailer(t2)
    table = r.get_xref_table()
    assert table[COSObjectKey(1, 0)].offset == 200  # newer wins
    assert table[COSObjectKey(2, 0)].offset == 250
    assert table[COSObjectKey(3, 0)].offset == 80   # older entry survives
    merged = r.get_trailer()
    assert merged is not None
    assert merged.get_int("Size") == 5  # newer wins
    assert merged.get_int("Prev") == 0  # older's /Prev fills in


def test_visited_offsets_tracks_sections_for_cycle_detection() -> None:
    r = XrefTrailerResolver()
    r.begin_section(100)
    r.begin_section(200)
    assert r.has_visited(100)
    assert r.has_visited(200)
    assert not r.has_visited(300)


def test_section_count_grows_per_call() -> None:
    r = XrefTrailerResolver()
    r.begin_section(1)
    r.begin_section(2)
    r.begin_section(3)
    assert r.section_count() == 3


def test_within_section_later_entry_overwrites_earlier() -> None:
    r = XrefTrailerResolver()
    r.begin_section(0)
    r.set_entry(COSObjectKey(1, 0), _entry(10))
    r.set_entry(COSObjectKey(1, 0), _entry(99))
    assert r.get_xref_table()[COSObjectKey(1, 0)].offset == 99


def test_get_trailer_returns_none_when_no_section_has_one() -> None:
    r = XrefTrailerResolver()
    r.begin_section(0)
    r.set_entry(COSObjectKey(1, 0), _entry(10))
    assert r.get_trailer() is None


def test_xref_entry_records_compressed_marker() -> None:
    e = XrefEntry(type=XrefType.COMPRESSED, offset=4, compressed_index=2)
    assert e.type is XrefType.COMPRESSED
    assert e.compressed_index == 2


def test_set_entry_before_section_raises() -> None:
    r = XrefTrailerResolver()
    import pytest
    with pytest.raises(RuntimeError):
        r.set_entry(COSObjectKey(1, 0), _entry(0))


def test_set_trailer_before_section_raises() -> None:
    r = XrefTrailerResolver()
    import pytest
    with pytest.raises(RuntimeError):
        r.set_trailer(COSDictionary())


def test_three_section_chain_resolution_order() -> None:
    """Confirm newer sections always take precedence regardless of how
    many are chained — exercises the merge loop direction."""
    r = XrefTrailerResolver()
    for i, off in enumerate([5000, 3000, 1000]):  # newest → oldest
        r.begin_section(off)
        r.set_entry(COSObjectKey(7, 0), _entry(off))
        t = COSDictionary()
        t.set_int("Marker", off)
        r.set_trailer(t)
        del i
    assert r.get_xref_table()[COSObjectKey(7, 0)].offset == 5000
    merged = r.get_trailer()
    assert merged is not None
    assert merged.get_int("Marker") == 5000


def test_trailer_keys_with_indirect_refs_propagate() -> None:
    """Trailer often holds /Root as an indirect reference; resolver must
    not require the value to be a particular COS subtype."""
    from pypdfbox.cos import COSObject

    r = XrefTrailerResolver()
    r.begin_section(0)
    t = COSDictionary()
    t.set_item("Root", COSObject(1, 0))
    t.set_int("Size", 2)
    r.set_trailer(t)
    merged = r.get_trailer()
    assert merged is not None
    assert isinstance(merged.get_item("Root"), COSObject)
    assert merged.get_int("Size") == 2


def test_int_helper_used_consistently() -> None:
    """Smoke test using COSInteger directly to make sure the trailer's
    typed accessors round-trip without the dictionary copy losing the
    ``COSInteger`` cache identity."""
    r = XrefTrailerResolver()
    r.begin_section(0)
    t = COSDictionary()
    t.set_item("X", COSInteger.get(7))
    r.set_trailer(t)
    merged = r.get_trailer()
    assert merged is not None
    assert merged.get_int("X") == 7
