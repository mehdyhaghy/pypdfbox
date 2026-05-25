"""Branch coverage for :class:`XrefTrailerResolver` — wave 1400.

Closes residual partial branches in
``pypdfbox/pdfparser/xref_trailer_resolver.py`` left after wave 1399:

* The ``while cur_obj.trailer is not None`` loop predicate exits the
  loop on entry when the startxref section has no trailer attached.
* The infinite-guard ``len(xref_seq_byte_pos) >= len(byte_pos_map)``
  fires the normal "continue" branch on a multi-/Prev chain.
* The "section.trailer is None" branch in the resolved-merge loop is
  taken when an older /Prev section is registered without a trailer.
"""

from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSObjectKey
from pypdfbox.pdfparser import XrefEntry, XrefTrailerResolver, XrefType


def _entry(offset: int) -> XrefEntry:
    return XrefEntry(type=XrefType.TABLE, offset=offset)


def test_set_startxref_section_without_trailer_falls_through_loop() -> None:
    """When the section at startxref has no trailer, the ``while
    cur_obj.trailer is not None`` predicate is False immediately —
    we exit the loop and proceed to the merge step with a single
    section recorded. Closes branch (266 → 284)."""
    r = XrefTrailerResolver()
    r.begin_section(1000)
    r.set_entry(COSObjectKey(7, 0), _entry(500))
    # Deliberately omit set_trailer — the section has no trailer.
    r.set_startxref(1000)
    # No trailer to merge — get_trailer falls back to the empty path,
    # but the xref table still picked up our entry.
    table = r.get_xref_table()
    assert table[COSObjectKey(7, 0)].offset == 500


def test_set_startxref_normal_prev_chain_loop_continues() -> None:
    """Three-section /Prev chain — the infinite-loop guard
    ``len(xref_seq) >= len(byte_pos_map)`` only fires *after* every
    section has been visited, so during the normal walk it stays
    False and the loop continues. Closes branch (281 → 266)."""
    r = XrefTrailerResolver()
    # Newest section reached via startxref.
    r.begin_section(3000)
    r.set_entry(COSObjectKey(1, 0), _entry(300))
    t1 = COSDictionary()
    t1.set_int("Size", 5)
    t1.set_int("Prev", 2000)
    r.set_trailer(t1)
    # Middle section in the chain.
    r.begin_section(2000)
    r.set_entry(COSObjectKey(2, 0), _entry(200))
    t2 = COSDictionary()
    t2.set_int("Size", 3)
    t2.set_int("Prev", 1000)
    r.set_trailer(t2)
    # Oldest section — terminates the chain (no /Prev).
    r.begin_section(1000)
    r.set_entry(COSObjectKey(3, 0), _entry(100))
    t3 = COSDictionary()
    t3.set_int("Size", 2)
    r.set_trailer(t3)

    r.set_startxref(3000)
    # All three sections' entries must be present in the resolved view.
    rt = r._resolved_xref_table  # noqa: SLF001 - testing resolved state
    assert rt is not None
    assert COSObjectKey(1, 0) in rt
    assert COSObjectKey(2, 0) in rt
    assert COSObjectKey(3, 0) in rt
    assert r.get_xref_type() is XrefType.TABLE


def test_set_startxref_chain_with_trailerless_older_section() -> None:
    """Newer section walks /Prev to an older section that has no
    trailer attached. The merge loop visits both, but skips the
    trailer-merge step for the trailerless one (section.trailer is
    None). Closes branch (291 → 299)."""
    r = XrefTrailerResolver()
    r.begin_section(2000)
    r.set_entry(COSObjectKey(1, 0), _entry(200))
    t1 = COSDictionary()
    t1.set_int("Size", 5)
    t1.set_int("Prev", 1000)
    r.set_trailer(t1)
    # Older section: registered with entries but no trailer.
    r.begin_section(1000)
    r.set_entry(COSObjectKey(2, 0), _entry(100))
    # Deliberately omit set_trailer.

    r.set_startxref(2000)
    rt = r._resolved_xref_table  # noqa: SLF001 - testing resolved state
    assert rt is not None
    # Both sections contributed entries even though the older one had
    # no trailer to merge.
    assert COSObjectKey(1, 0) in rt
    assert COSObjectKey(2, 0) in rt
    resolved = r._resolved_trailer  # noqa: SLF001 - testing resolved state
    # Only the newer section's trailer made it through the merge.
    assert resolved is not None
    assert resolved.get_int("Size") == 5


def test_next_xref_obj_tolerates_subclass_dropping_current_section() -> None:
    """``next_xref_obj`` defensively re-checks ``self._current is not
    None`` after ``begin_section`` because subclasses might override
    begin_section to be a no-op. Force the False branch via a subclass
    that drops the section to confirm we don't crash.

    Closes branch (103 → -94)."""

    class _NoOpResolver(XrefTrailerResolver):
        def begin_section(self, start_offset: int) -> None:
            # Deliberately drop the assignment; tests the defensive
            # guard at line 103.
            self._current = None

    r = _NoOpResolver()
    # Must not raise — the guard short-circuits the xref_type write.
    r.next_xref_obj(1234, XrefType.TABLE)
    assert r._current is None  # noqa: SLF001


def test_set_startxref_full_chain_hits_infinite_loop_guard() -> None:
    """Construct a chain longer than expected so the guard
    ``len(xref_seq_byte_pos) >= len(byte_pos_map)`` actually fires
    on the final iteration — confirms it terminates without infinite
    looping on a synthetic /Prev cycle."""
    r = XrefTrailerResolver()
    # Two sections that point at *each other* via /Prev → infinite
    # cycle without the guard.
    r.begin_section(2000)
    t1 = COSDictionary()
    t1.set_int("Prev", 1000)
    r.set_trailer(t1)
    r.begin_section(1000)
    t2 = COSDictionary()
    t2.set_int("Prev", 2000)
    r.set_trailer(t2)

    r.set_startxref(2000)
    # Guard must have fired — we got back a finite resolved view.
    assert r._resolved_trailer is not None  # noqa: SLF001
