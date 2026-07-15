"""Structure-tree clone parity after the O(1)-per-element split speedups.

``Splitter.clone_structure_tree`` was made near-linear by (a) flattening the
source /ParentTree once per ``split()`` run instead of per chunk, (b)
replacing the per-element ``page_tree.index_of`` walk with a precomputed
``{id(page_dict): index}`` map, and (c) iterating pages directly instead of
``range(len)`` + ``get(i)``. The cloned output must be byte-for-byte
identical to the naive implementation; these tests pin the observable
structure of a split tagged document.
"""

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSInteger,
    COSName,
)
from pypdfbox.multipdf.splitter import Splitter
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage


def _n(s: str) -> COSName:
    return COSName.get_pdf_name(s)


def _build_tagged(pages: int) -> PDDocument:
    """One /P structure element per page, plus a /ParentTree /Nums entry
    per page keyed by the page's /StructParents value."""
    doc = PDDocument()
    struct_root = COSDictionary()
    struct_root.set_item(_n("Type"), _n("StructTreeRoot"))
    k_array = COSArray()
    nums = COSArray()
    for i in range(pages):
        page = PDPage()
        pd = page.get_cos_object()
        pd.set_item(_n("StructParents"), COSInteger.get(i))
        doc.add_page(page)

        elem = COSDictionary()
        elem.set_item(_n("S"), _n("P"))
        elem.set_item(_n("Pg"), pd)
        elem.set_item(_n("K"), COSInteger.get(0))
        elem.set_item(_n("P"), struct_root)
        k_array.add(elem)

        nums.add(COSInteger.get(i))
        holder = COSArray()
        holder.add(elem)
        nums.add(holder)

    struct_root.set_item(_n("K"), k_array)
    parent_tree = COSDictionary()
    parent_tree.set_item(_n("Nums"), nums)
    struct_root.set_item(_n("ParentTree"), parent_tree)
    struct_root.set_item(_n("ParentTreeNextKey"), COSInteger.get(pages))
    catalog = doc.get_document_catalog().get_cos_object()
    catalog.set_item(_n("StructTreeRoot"), struct_root)
    mark_info = COSDictionary()
    mark_info.set_boolean(_n("Marked"), True)
    catalog.set_item(_n("MarkInfo"), mark_info)
    return doc


def _struct_root(chunk: PDDocument) -> COSDictionary:
    return chunk.get_document_catalog().get_cos_object().get_dictionary_object(
        _n("StructTreeRoot")
    )


def test_single_page_chunks_each_keep_their_own_element() -> None:
    doc = _build_tagged(6)
    try:
        splitter = Splitter()
        splitter.set_split_at_page(1)
        chunks = splitter.split(doc)
        try:
            assert len(chunks) == 6
            for chunk in chunks:
                root = _struct_root(chunk)
                assert root is not None
                k = root.get_dictionary_object(_n("K"))
                assert isinstance(k, COSArray)
                # Exactly one page in the chunk -> exactly one element kept.
                assert k.size() == 1
                elem = k.get_object(0)
                assert elem.get_name(_n("S")) == "P"
                # /Pg must point at the chunk's own imported page dict.
                pg = elem.get_dictionary_object(_n("Pg"))
                chunk_page = chunk.get_pages().get(0).get_cos_object()
                assert pg is chunk_page
                # A fresh, narrowed /ParentTree is present.
                pt = root.get_dictionary_object(_n("ParentTree"))
                assert isinstance(pt, COSDictionary)
                narrowed = pt.get_dictionary_object(_n("Nums"))
                assert isinstance(narrowed, COSArray)
                assert narrowed.size() == 2  # one key + one value holder
        finally:
            for chunk in chunks:
                chunk.close()
    finally:
        doc.close()


def test_multi_page_chunks_keep_all_member_elements() -> None:
    doc = _build_tagged(6)
    try:
        splitter = Splitter()
        splitter.set_split_at_page(2)
        chunks = splitter.split(doc)
        try:
            assert len(chunks) == 3
            for chunk in chunks:
                root = _struct_root(chunk)
                k = root.get_dictionary_object(_n("K"))
                assert isinstance(k, COSArray)
                assert k.size() == 2
                chunk_page_dicts = {
                    id(chunk.get_pages().get(i).get_cos_object())
                    for i in range(len(chunk.get_pages()))
                }
                for j in range(k.size()):
                    elem = k.get_object(j)
                    pg = elem.get_dictionary_object(_n("Pg"))
                    # Each retained element points at a page in THIS chunk.
                    assert id(pg) in chunk_page_dicts
                pt = root.get_dictionary_object(_n("ParentTree"))
                narrowed = pt.get_dictionary_object(_n("Nums"))
                assert isinstance(narrowed, COSArray)
                assert narrowed.size() == 4  # two (key, value) pairs
        finally:
            for chunk in chunks:
                chunk.close()
    finally:
        doc.close()


def test_parent_tree_flatten_shared_across_chunks_gives_stable_output() -> None:
    """Two independent splits of identical documents produce the same
    per-chunk element counts — the shared source-/ParentTree flatten must
    not leak state between chunks or between runs."""
    counts = []
    for _ in range(2):
        doc = _build_tagged(5)
        try:
            splitter = Splitter()
            splitter.set_split_at_page(1)
            chunks = splitter.split(doc)
            try:
                counts.append(
                    [
                        _struct_root(c)
                        .get_dictionary_object(_n("K"))
                        .size()
                        for c in chunks
                    ]
                )
            finally:
                for c in chunks:
                    c.close()
        finally:
            doc.close()
    assert counts[0] == counts[1] == [1, 1, 1, 1, 1]
