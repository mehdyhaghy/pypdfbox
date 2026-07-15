"""Regression tests for ScratchFile's O(1) shadow structures.

These lock in the performance-fix invariants added to
``pypdfbox.io.scratch_file``:

* ``_mem_page_count`` mirrors the number of non-None ``_mem_pages`` entries
  (drives the MIXED-mode spill decision without an O(pages) rescan).
* ``_free_pages_set`` mirrors ``_free_pages`` membership (drives the
  ``mark_pages_as_free`` duplicate check without an O(free) list scan), while
  ``_free_pages`` remains the LIFO ordering authority.

The behaviour under test is unchanged from upstream ScratchFile; only the
internal bookkeeping is new, so these assert the shadow state stays in sync
across every mutation path.
"""

from __future__ import annotations

from pypdfbox.io import MemoryUsageSetting, ScratchFile
from pypdfbox.io.scratch_file import NO_FREE_PAGE


def _mem_count(sf: ScratchFile) -> int:
    return sum(1 for p in sf._mem_pages if p is not None)


def test_mem_page_count_tracks_main_memory_pages() -> None:
    sf = ScratchFile()  # MAIN_MEMORY_ONLY
    try:
        for _ in range(20):
            sf.get_new_page()
        assert sf._mem_page_count == _mem_count(sf) == 20
    finally:
        sf.close()
    assert sf._mem_page_count == 0


def test_mem_page_count_matches_across_spill_boundary() -> None:
    # MIXED with a cap of 4 pages -> after 4 in-RAM pages the rest spill.
    page_size = 4096
    setting = MemoryUsageSetting.setup_mixed(max_main_memory_bytes=4 * page_size)
    sf = ScratchFile(setting, page_size=page_size)
    try:
        for _ in range(10):
            sf.get_new_page()
        # Only the pages that fit under the cap stay in RAM; the rest are None.
        assert sf._mem_page_count == _mem_count(sf)
        assert sf._mem_page_count <= 4
        # Some pages must have spilled to the temp file for this to be a
        # meaningful spill-boundary test.
        assert sf._mem_page_count < 10
    finally:
        sf.close()


def test_free_pages_set_mirrors_list_and_preserves_lifo() -> None:
    sf = ScratchFile()
    try:
        pages = [sf.get_new_page() for _ in range(6)]
        # Free three specific pages; set membership must match the list.
        sf.mark_pages_as_free([pages[1], pages[3], pages[5]])
        assert set(sf._free_pages) == sf._free_pages_set
        assert sf._free_pages_set == {pages[1], pages[3], pages[5]}

        # Duplicate free is ignored (the O(1) set check), list stays unchanged.
        before = list(sf._free_pages)
        sf.mark_pages_as_free([pages[3]])
        assert sf._free_pages == before

        # get_new_page reuses in strict LIFO order (last freed pops first).
        assert sf.get_new_page() == pages[5]
        assert sf.get_new_page() == pages[3]
        assert sf.get_new_page() == pages[1]
        assert sf._free_pages == []
        assert sf._free_pages_set == set()
    finally:
        sf.close()


def test_dequeue_page_keeps_set_in_sync() -> None:
    sf = ScratchFile()
    try:
        a = sf.get_new_page()
        b = sf.get_new_page()
        sf.enqueue_page(a)
        sf.enqueue_page(b)
        assert sf._free_pages_set == {a, b}
        assert sf.dequeue_page() == b  # LIFO
        assert sf._free_pages_set == {a}
        assert sf.dequeue_page() == a
        assert sf._free_pages_set == set()
        assert sf.dequeue_page() == NO_FREE_PAGE
    finally:
        sf.close()
