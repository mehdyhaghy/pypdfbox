"""Wave 1370 — Splitter round-out (agent E).

Covers split semantics not already nailed down by the existing splitter
suite:

- Split-by-page configurations: fluent chaining of setters returns self;
  setter+split round-trip produces the configured chunk count.
- Custom subclass ``split_at_page`` override (the upstream hook used to
  implement bookmark-driven and other custom split rules) actually
  drives chunk boundaries.
- Splitter does NOT carry ``/OpenAction`` from source catalog into each
  chunk's catalog (parity with upstream — chunks are independent docs
  whose viewers shouldn't auto-trigger source's open action).
- Splitter does NOT carry ``/Names`` legacy ``/Dests`` from source.
- Split chunks contain blank pages when the chunk-size > 1 and the
  tail chunk has fewer source pages than the chunk size (chunk size is
  a hard upper bound, NOT a fixed page count).
- Splitter result chunks are independently saveable/loadable.
"""
from __future__ import annotations

from pathlib import Path

from pypdfbox import PDDocument, PDPage
from pypdfbox.cos import COSArray, COSDictionary, COSName, COSStream
from pypdfbox.multipdf import Splitter

_OPEN_ACTION = COSName.get_pdf_name("OpenAction")
_NAMES = COSName.get_pdf_name("Names")
_DESTS = COSName.get_pdf_name("Dests")


def _make_doc(n_pages: int, marker_prefix: bytes = b"% Page") -> PDDocument:
    doc = PDDocument()
    for i in range(n_pages):
        page = PDPage()
        s = COSStream()
        s.set_raw_data(marker_prefix + b" " + str(i).encode("ascii") + b"\n")
        page.set_contents(s)
        doc.add_page(page)
    return doc


# ---------- fluent setter / round-trip ----------


def test_setters_fluent_chaining_returns_self() -> None:
    splitter = Splitter()
    chained = splitter.set_split_at_page(2).set_start_page(1).set_end_page(10)
    assert chained is splitter


def test_split_with_blank_tail_chunk(tmp_path: Path) -> None:
    """7 pages, chunk size 3 → 3 + 3 + 1. The third chunk is short, NOT
    padded with blanks. (Verifies our parity with upstream: chunk-size is
    a hard upper bound, the tail is short.)"""
    src = _make_doc(7)
    splitter = Splitter()
    splitter.set_split_at_page(3)
    chunks = splitter.split(src)
    sizes = [c.get_number_of_pages() for c in chunks]
    assert sizes == [3, 3, 1]
    # Each chunk independently roundtrips through save/load.
    for i, chunk in enumerate(chunks):
        out_path = tmp_path / f"chunk_{i}.pdf"
        chunk.save(out_path)
    for c in chunks:
        c.close()
    src.close()
    # Verify the saved chunks can be reloaded with the expected page count.
    for i, sz in enumerate(sizes):
        with PDDocument.load(tmp_path / f"chunk_{i}.pdf") as reopened:
            assert reopened.get_number_of_pages() == sz


# ---------- custom split_at_page subclass hook ----------


class _BookmarkLikeSplitter(Splitter):
    """Splits at a fixed list of 0-based page numbers — the model an
    outline/bookmark-driven splitter would use to drop chunks at section
    boundaries."""

    def __init__(self, break_pages: set[int]) -> None:
        super().__init__()
        self._break_pages = set(break_pages)

    def split_at_page(self, page_number: int) -> bool:  # type: ignore[override]
        # Match upstream: page_number is 0-based; True ⇒ new chunk
        # starts BEFORE this page. Break before page 0 has no effect
        # (the first chunk is always created).
        return page_number in self._break_pages


def test_subclass_split_at_page_drives_chunk_boundaries() -> None:
    """A custom Splitter subclass that overrides ``split_at_page`` rules
    chunk allocation. Mirrors how a bookmark-driven splitter would plug
    in upstream (subclassing PDFBox's Splitter and overriding
    ``splitAtPage``)."""
    src = _make_doc(6)
    # Break before pages 0, 2, 4 → chunks at [0,1], [2,3], [4,5].
    splitter = _BookmarkLikeSplitter(break_pages={0, 2, 4})
    chunks = splitter.split(src)
    sizes = [c.get_number_of_pages() for c in chunks]
    assert sizes == [2, 2, 2]
    for c in chunks:
        c.close()
    src.close()


def test_subclass_split_at_page_with_single_chunk() -> None:
    """Overriding ``split_at_page`` to always return False produces one
    big chunk."""

    class _NeverSplit(Splitter):
        def split_at_page(self, page_number: int) -> bool:  # type: ignore[override]
            return False

    src = _make_doc(5)
    splitter = _NeverSplit()
    chunks = splitter.split(src)
    assert len(chunks) == 1
    assert chunks[0].get_number_of_pages() == 5
    for c in chunks:
        c.close()
    src.close()


# ---------- /OpenAction not carried into chunks ----------


def test_split_does_not_carry_open_action_into_chunks() -> None:
    """Source's /OpenAction must NOT leak into chunk catalogs. Each chunk
    is an independent document whose first page may not be the source's
    /OpenAction target, so the action would be meaningless / dangerous."""
    src = _make_doc(4)
    # Install /OpenAction on source pointing at page index 2.
    action = COSDictionary()
    action.set_name("S", "GoTo")
    dest = COSArray()
    dest.add(src.get_page(2).get_cos_object())
    dest.add(COSName.get_pdf_name("Fit"))
    action.set_item(COSName.get_pdf_name("D"), dest)
    src.get_document_catalog().get_cos_object().set_item(_OPEN_ACTION, action)

    splitter = Splitter()
    chunks = splitter.split(src)
    try:
        # Every chunk catalog: no /OpenAction.
        for chunk in chunks:
            catalog_dict = chunk.get_document_catalog().get_cos_object()
            assert catalog_dict.get_dictionary_object(_OPEN_ACTION) is None
    finally:
        for c in chunks:
            c.close()
        src.close()


# ---------- /Names tree not carried into chunks ----------


def test_split_does_not_carry_legacy_dests_tree_into_chunks() -> None:
    """The source's catalog-level /Names /Dests tree is NOT copied
    into each chunk's catalog. Source-side named destinations get
    resolved at link-stage time via ``_stage_link_destination`` — the
    raw name tree itself isn't propagated."""
    src = _make_doc(3)
    # Build a /Names /Dests structure on the source.
    names_root = COSDictionary()
    dests_root = COSDictionary()
    leaf = COSArray()
    leaf.add(COSName.get_pdf_name("MyDest"))
    inner_array = COSArray()
    inner_array.add(src.get_page(1).get_cos_object())
    inner_array.add(COSName.get_pdf_name("Fit"))
    leaf.add(inner_array)
    dests_root.set_item(COSName.get_pdf_name("Names"), leaf)
    names_root.set_item(_DESTS, dests_root)
    src.get_document_catalog().get_cos_object().set_item(_NAMES, names_root)

    chunks = Splitter().split(src)
    try:
        for chunk in chunks:
            catalog_dict = chunk.get_document_catalog().get_cos_object()
            # /Names absent on chunks (upstream parity: splitter
            # produces independent docs; the /Names tree isn't replicated).
            assert catalog_dict.get_dictionary_object(_NAMES) is None
    finally:
        for c in chunks:
            c.close()
        src.close()


# ---------- save round-trip + page identity ----------


def test_split_chunks_save_independently(tmp_path: Path) -> None:
    """Each split chunk can be saved to its own file and reopened with
    the expected page count. Verifies cross-document resource sharing
    doesn't leak post-save (the source must outlive the splits, but
    saving each chunk doesn't require chunks to share state)."""
    src = _make_doc(5)
    splitter = Splitter().set_split_at_page(2)
    chunks = splitter.split(src)

    out_paths = []
    for i, chunk in enumerate(chunks):
        path = tmp_path / f"chunk_{i}.pdf"
        chunk.save(path)
        out_paths.append(path)
    # Close all chunks BEFORE closing the source — chunk lifetimes may
    # share pages with src until save completes.
    for c in chunks:
        c.close()
    src.close()

    sizes = []
    for path in out_paths:
        with PDDocument.load(path) as reopened:
            sizes.append(reopened.get_number_of_pages())
    assert sizes == [2, 2, 1]


def test_split_with_range_drops_pages_outside_range() -> None:
    """Setting start/end skips pages outside the range; chunks contain
    only in-range pages."""
    src = _make_doc(10)
    splitter = Splitter()
    splitter.set_start_page(3)
    splitter.set_end_page(5)
    splitter.set_split_at_page(10)  # single chunk holds the whole range
    chunks = splitter.split(src)
    assert len(chunks) == 1
    assert chunks[0].get_number_of_pages() == 3
    for c in chunks:
        c.close()
    src.close()
