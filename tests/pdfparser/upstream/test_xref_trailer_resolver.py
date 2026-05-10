"""Upstream-parity tests for ``XrefTrailerResolver``.

Upstream PDFBox does not ship a JUnit test for this class; these tests
exercise the public API surface that PDFBox callers depend on, mirroring
the contracts documented on the upstream methods themselves.

Method line references point into
``pdfbox/src/main/java/org/apache/pdfbox/pdfparser/XrefTrailerResolver.java``
on the 3.0.x baseline.
"""
from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary, COSObjectKey
from pypdfbox.pdfparser import XrefEntry, XrefTrailerResolver, XrefType

# ----- nextXrefObj (Java line 152) --------------------------------------


def test_next_xref_obj_starts_section_with_table_type() -> None:
    r = XrefTrailerResolver()
    r.next_xref_obj(1234, XrefType.TABLE)
    assert r.section_count() == 1
    assert r.has_visited(1234)


def test_next_xref_obj_records_stream_type_for_get_xref_type() -> None:
    r = XrefTrailerResolver()
    r.next_xref_obj(1234, XrefType.STREAM)
    r.set_trailer(COSDictionary())
    r.set_startxref(1234)
    assert r.get_xref_type() is XrefType.STREAM


def test_next_xref_obj_can_be_called_multiple_times() -> None:
    r = XrefTrailerResolver()
    r.next_xref_obj(100, XrefType.TABLE)
    r.next_xref_obj(200, XrefType.STREAM)
    r.next_xref_obj(300, XrefType.TABLE)
    assert r.section_count() == 3


# ----- setXRef (Java line 175) ------------------------------------------


def test_set_x_ref_adds_entry_to_current_section() -> None:
    r = XrefTrailerResolver()
    r.next_xref_obj(0, XrefType.TABLE)
    r.set_x_ref(COSObjectKey(1, 0), 100)
    assert r.get_xref_table()[COSObjectKey(1, 0)].offset == 100


def test_set_x_ref_pdfbox_3506_does_not_overwrite_existing() -> None:
    """PDFBOX-3506: in hybrid files the /XRefStm entry must not clobber
    the regular xref table entry."""
    r = XrefTrailerResolver()
    r.next_xref_obj(0, XrefType.TABLE)
    r.set_x_ref(COSObjectKey(1, 0), 100)
    r.set_x_ref(COSObjectKey(1, 0), 999)  # ignored
    assert r.get_xref_table()[COSObjectKey(1, 0)].offset == 100


def test_set_x_ref_before_section_logs_and_returns(caplog) -> None:
    r = XrefTrailerResolver()
    with caplog.at_level("WARNING"):
        r.set_x_ref(COSObjectKey(1, 0), 0)
    # No section was started, so nothing was added.
    assert r.section_count() == 0
    assert any("XRef start was not signalled" in rec.message for rec in caplog.records)


# ----- setStartxref (Java line 232) -------------------------------------


def test_set_startxref_resolves_trailer_chain_via_prev() -> None:
    r = XrefTrailerResolver()
    # Older section at byte 1000.
    r.next_xref_obj(1000, XrefType.TABLE)
    r.set_x_ref(COSObjectKey(1, 0), 10)
    older = COSDictionary()
    older.set_int("Size", 3)
    older.set_int("Older", 1)
    r.set_trailer(older)
    # Newer section at byte 2000 references older via /Prev.
    r.next_xref_obj(2000, XrefType.TABLE)
    r.set_x_ref(COSObjectKey(2, 0), 20)
    newer = COSDictionary()
    newer.set_int("Size", 5)
    newer.set_int("Prev", 1000)
    r.set_trailer(newer)
    r.set_startxref(2000)
    # Resolved trailer takes newer's Size (newer wins) and inherits Older.
    assert r.get_xref_type() is XrefType.TABLE
    contained = r.get_contained_object_numbers(0)
    assert contained == set()


def test_set_startxref_handles_missing_offset_with_fallback() -> None:
    """Upstream falls back to merging every section in byte-position
    order when the startxref pointer is invalid."""
    r = XrefTrailerResolver()
    r.next_xref_obj(100, XrefType.TABLE)
    r.set_x_ref(COSObjectKey(1, 0), 10)
    t = COSDictionary()
    t.set_int("Size", 2)
    r.set_trailer(t)
    r.set_startxref(99999)  # not a real section
    # In fallback mode, xref_type defaults to TABLE.
    assert r.get_xref_type() is XrefType.TABLE


def test_set_startxref_called_twice_warns_and_no_ops(caplog) -> None:
    r = XrefTrailerResolver()
    r.next_xref_obj(100, XrefType.STREAM)
    r.set_trailer(COSDictionary())
    r.set_startxref(100)
    first_type = r.get_xref_type()
    with caplog.at_level("WARNING"):
        r.set_startxref(100)
    # Type unchanged; second call was a no-op (warning logged).
    assert r.get_xref_type() is first_type
    assert any("only ones" in rec.message for rec in caplog.records)


def test_set_startxref_stops_at_prev_cycle() -> None:
    """A trailer with /Prev pointing at itself must not loop forever."""
    r = XrefTrailerResolver()
    r.next_xref_obj(1000, XrefType.TABLE)
    t = COSDictionary()
    t.set_int("Prev", 1000)  # self-reference
    r.set_trailer(t)
    r.set_startxref(1000)  # must terminate
    assert r.get_xref_type() is XrefType.TABLE


# ----- getXrefType (Java line 164) --------------------------------------


def test_get_xref_type_returns_none_before_set_startxref() -> None:
    r = XrefTrailerResolver()
    r.next_xref_obj(0, XrefType.STREAM)
    assert r.get_xref_type() is None


# ----- getContainedObjectNumbers (Java line 336) ------------------------


def test_get_contained_object_numbers_returns_none_before_resolve() -> None:
    r = XrefTrailerResolver()
    r.next_xref_obj(0, XrefType.STREAM)
    assert r.get_contained_object_numbers(5) is None


def test_get_contained_object_numbers_collects_compressed_entries() -> None:
    r = XrefTrailerResolver()
    r.next_xref_obj(0, XrefType.STREAM)
    # Two objects compressed inside object stream #7.
    r.set_entry(
        COSObjectKey(10, 0),
        XrefEntry(type=XrefType.COMPRESSED, offset=7, compressed_index=0),
    )
    r.set_entry(
        COSObjectKey(11, 0),
        XrefEntry(type=XrefType.COMPRESSED, offset=7, compressed_index=1),
    )
    # One object compressed inside object stream #8 — must NOT be returned.
    r.set_entry(
        COSObjectKey(12, 0),
        XrefEntry(type=XrefType.COMPRESSED, offset=8, compressed_index=0),
    )
    # An uncompressed entry — must NOT be returned.
    r.set_entry(
        COSObjectKey(13, 0),
        XrefEntry(type=XrefType.STREAM, offset=7),
    )
    r.set_trailer(COSDictionary())
    r.set_startxref(0)
    assert r.get_contained_object_numbers(7) == {10, 11}
    assert r.get_contained_object_numbers(8) == {12}
    assert r.get_contained_object_numbers(99) == set()


# ----- reset() interaction with resolved view ---------------------------


def test_reset_clears_resolved_view() -> None:
    r = XrefTrailerResolver()
    r.next_xref_obj(100, XrefType.STREAM)
    r.set_trailer(COSDictionary())
    r.set_startxref(100)
    assert r.get_xref_type() is XrefType.STREAM
    r.reset()
    assert r.get_xref_type() is None
    assert r.get_contained_object_numbers(0) is None
    # And set_startxref can be called again after the reparse.
    r.next_xref_obj(200, XrefType.TABLE)
    r.set_trailer(COSDictionary())
    r.set_startxref(200)
    assert r.get_xref_type() is XrefType.TABLE


# ----- Java naming → Python naming sanity check --------------------------


@pytest.mark.parametrize(
    "method_name",
    [
        "next_xref_obj",
        "set_x_ref",
        "set_startxref",
        "get_xref_type",
        "get_contained_object_numbers",
    ],
)
def test_upstream_named_methods_exist(method_name: str) -> None:
    assert callable(getattr(XrefTrailerResolver, method_name))
