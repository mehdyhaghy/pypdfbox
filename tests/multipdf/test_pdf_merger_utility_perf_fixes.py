"""Regression tests for the three merge-path performance fixes.

These pin *behaviour* (not timing): the optimized fast paths must produce
output byte-identical to the original algorithms.

  * Fix 1 — AcroForm legacy/join merge: the O(F^2) ``get_field`` collision
    probe was replaced (for the real :class:`PDAcroForm`) by an incrementally
    grown FQN set. Collision/rename decisions must be unchanged, including
    collisions against previously appended source fields and against fields
    nested inside an appended subtree.
  * Fix 2 — multi-document struct-tree merge: the destination ``/ParentTree``
    is cached across appends instead of being re-flattened each time. The
    merged ``/Nums`` must be unchanged.
  * Fix 3 — optimize-mode resource dedup: an ``id(value)`` digest memo avoids
    re-hashing a shared subgraph per page. Digests and dedup output unchanged.
"""
from __future__ import annotations

import io

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName
from pypdfbox.multipdf.pdf_merger_utility import (
    DocumentMergeMode,
    PDFMergerUtility,
)
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage


def _n(s: str) -> COSName:
    return COSName.get_pdf_name(s)


def _field(partial: str, kids: list[COSDictionary] | None = None) -> COSDictionary:
    f = COSDictionary()
    f.set_item(_n("FT"), _n("Tx"))
    f.set_string(_n("T"), partial)
    if kids:
        arr = COSArray()
        for k in kids:
            arr.add(k)
        f.set_item(_n("Kids"), arr)
    return f


def _form_doc(field_dicts: list[COSDictionary]) -> PDDocument:
    doc = PDDocument()
    doc.add_page(PDPage())
    catalog = doc.get_document_catalog().get_cos_object()
    acro = COSDictionary()
    arr = COSArray()
    for fd in field_dicts:
        arr.add(fd)
    acro.set_item(_n("Fields"), arr)
    catalog.set_item(_n("AcroForm"), acro)
    return doc


def _merged_field_names(dest: PDDocument) -> list[str | None]:
    acro = dest.get_document_catalog().get_cos_object().get_dictionary_object(
        _n("AcroForm")
    )
    arr = acro.get_dictionary_object(_n("Fields"))
    return [arr.get_object(i).get_string(_n("T")) for i in range(arr.size())]


# --------------------------------------------------------------------------
# Fix 1 — AcroForm collision / rename parity on the real PDAcroForm fast path
# --------------------------------------------------------------------------


def test_fix1_colliding_top_level_names_are_renamed() -> None:
    # dest already carries a dummyFieldName5 so the counter must resume at 6.
    dest = _form_doc([_field("A"), _field("B"), _field("C"), _field("dummyFieldName5")])
    src = _form_doc([_field("A"), _field("X"), _field("C")])
    try:
        PDFMergerUtility().append_document(dest, src)
        # A and C collide with the destination -> renamed to the next free
        # dummyFieldName suffixes (6, 7); X is unique and keeps its name.
        assert _merged_field_names(dest) == [
            "A",
            "B",
            "C",
            "dummyFieldName5",
            "dummyFieldName6",
            "X",
            "dummyFieldName7",
        ]
    finally:
        dest.close()
        src.close()


def test_fix1_no_collision_keeps_all_names() -> None:
    dest = _form_doc([_field(f"d{i}") for i in range(5)])
    src = _form_doc([_field(f"s{i}") for i in range(5)])
    try:
        PDFMergerUtility().append_document(dest, src)
        assert _merged_field_names(dest) == [
            "d0", "d1", "d2", "d3", "d4", "s0", "s1", "s2", "s3", "s4",
        ]
    finally:
        dest.close()
        src.close()


def test_fix1_collision_against_previously_appended_source_field() -> None:
    # Destination starts EMPTY (no /Fields collisions) but the source has two
    # fields with the SAME name. The second must collide with the first
    # appended field and be renamed — the incremental FQN set must reflect
    # in-progress additions, exactly as the old live-rewalk get_field did.
    dest = _form_doc([])
    src = _form_doc([_field("dup"), _field("dup")])
    try:
        PDFMergerUtility().append_document(dest, src)
        names = _merged_field_names(dest)
        assert names[0] == "dup"
        assert names[1] == "dummyFieldName1"
    finally:
        dest.close()
        src.close()


def test_fix1_collision_against_nested_appended_subtree() -> None:
    # A source top-level field WITHOUT /T but with a kid "leaf" produces a
    # single-token FQN "leaf" once appended. A later source top-level field
    # named "leaf" must collide with that nested field — proving the FQN set
    # tracks the whole appended subtree, not just the top field.
    parentless = COSDictionary()  # no /T, one kid with /T "leaf"
    parentless.set_item(_n("FT"), _n("Tx"))
    kid = _field("leaf")
    kids = COSArray()
    kids.add(kid)
    parentless.set_item(_n("Kids"), kids)

    dest = _form_doc([])
    src = _form_doc([parentless, _field("leaf")])
    try:
        PDFMergerUtility().append_document(dest, src)
        names = _merged_field_names(dest)
        # second top-level source field "leaf" collides with the nested leaf.
        assert names[-1] == "dummyFieldName1"
    finally:
        dest.close()
        src.close()


# --------------------------------------------------------------------------
# Fix 2 — cached ParentTree across successive appends
# --------------------------------------------------------------------------


def _parent_tree_keys(dest: PDDocument) -> list[int]:
    sr = dest.get_document_catalog().get_cos_object().get_dictionary_object(
        _n("StructTreeRoot")
    )
    pt = sr.get_dictionary_object(_n("ParentTree"))
    arr = pt.get_dictionary_object(_n("Nums"))
    return [
        arr.get_object(i).int_value()
        for i in range(0, arr.size(), 2)
        if isinstance(arr.get_object(i), COSInteger)
    ]


def _run_tagged_merge(source_bytes: bytes, appends: int, disable_cache: bool):
    m = PDFMergerUtility()
    if disable_cache:
        # Neutralise the cache -> force a fresh flatten on every append.
        m._cached_dest_parent_tree_map = (  # type: ignore[method-assign]  # noqa: SLF001
            lambda st, pt: PDFMergerUtility.get_number_tree_as_map(pt)
        )
    dest = PDDocument.load(source_bytes)
    for _ in range(appends):
        src = PDDocument.load(source_bytes)
        m.append_document(dest, src)
        src.close()
    keys = _parent_tree_keys(dest)
    dest.close()
    return keys


def _tagged_source_bytes() -> bytes | None:
    import pathlib

    for p in pathlib.Path("tests/fixtures").rglob("*.pdf"):
        try:
            d = PDDocument.load(str(p))
            sr = d.get_document_catalog().get_struct_tree_root()
            has = sr is not None and sr.get_parent_tree() is not None
            d.close()
            if has:
                return p.read_bytes()
        except Exception:
            continue
    return None


def test_fix2_cached_parent_tree_matches_uncached() -> None:
    import pytest

    data = _tagged_source_bytes()
    if data is None:
        pytest.skip("no bundled tagged PDF with a /ParentTree available")
    cached = _run_tagged_merge(data, appends=4, disable_cache=False)
    fresh = _run_tagged_merge(data, appends=4, disable_cache=True)
    assert cached == fresh
    # The parent tree must actually grow across appends (merge really fired).
    assert len(cached) > 1


def test_fix2_cache_keyed_by_struct_root_identity() -> None:
    import pytest

    data = _tagged_source_bytes()
    if data is None:
        pytest.skip("no bundled tagged PDF with a /ParentTree available")
    m = PDFMergerUtility()
    assert m._parent_tree_map_cache is None  # noqa: SLF001
    dest = PDDocument.load(data)
    src = PDDocument.load(data)
    m.append_document(dest, src)
    src.close()
    cache = m._parent_tree_map_cache  # noqa: SLF001
    assert cache is not None
    root_cos = dest.get_document_catalog().get_struct_tree_root().get_cos_object()
    # cache key is the destination StructTreeRoot COS object identity.
    assert cache[0] is root_cos
    dest.close()


# --------------------------------------------------------------------------
# Fix 3 — id(value) digest memo
# --------------------------------------------------------------------------


def test_fix3_memo_digest_matches_unmemoized() -> None:
    d = COSDictionary()
    d.set_item(_n("BaseFont"), _n("Helvetica"))
    d.set_item(_n("Subtype"), _n("Type1"))
    plain = PDFMergerUtility._canonical_resource_hash(d)  # noqa: SLF001
    memo: dict[int, bytes | None] = {}
    first = PDFMergerUtility._canonical_resource_hash(d, memo)  # noqa: SLF001
    second = PDFMergerUtility._canonical_resource_hash(d, memo)  # noqa: SLF001
    assert plain == first == second
    assert id(d) in memo


def test_fix3_memo_caches_unhashable_as_none() -> None:
    cyc = COSDictionary()
    arr = COSArray()
    arr.add(cyc)
    cyc.set_item(_n("Self"), arr)  # cycle -> unhashable
    memo: dict[int, bytes | None] = {}
    result = PDFMergerUtility._canonical_resource_hash(cyc, memo)  # noqa: SLF001
    assert result is None
    assert id(cyc) in memo
    assert memo[id(cyc)] is None
    # a second call is served from the memo and still returns None
    assert PDFMergerUtility._canonical_resource_hash(cyc, memo) is None  # noqa: SLF001


def _optimize_source_bytes() -> bytes:
    doc = PDDocument()
    page1 = PDPage()
    doc.add_page(page1)
    res = COSDictionary()
    font = COSDictionary()
    fd = COSDictionary()
    fd.set_item(_n("BaseFont"), _n("Helvetica"))
    fd.set_item(_n("Subtype"), _n("Type1"))
    font.set_item(_n("F1"), fd)
    res.set_item(_n("Font"), font)
    page1.get_cos_object().set_item(_n("Resources"), res)
    page2 = PDPage()
    page2.get_cos_object().set_item(_n("Resources"), res)  # shares the font
    doc.add_page(page2)
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


def test_fix3_optimize_dedup_output_unchanged_by_memo() -> None:
    src = _optimize_source_bytes()
    merger = PDFMergerUtility()
    merger.set_document_merge_mode(DocumentMergeMode.OPTIMIZE_RESOURCES_MODE)
    merger.add_source(io.BytesIO(src))
    merger.add_source(io.BytesIO(src))
    out = io.BytesIO()
    merger.set_destination_stream(out)
    merger.merge_documents()

    result = PDDocument.load(out.getvalue())
    try:
        assert result.get_number_of_pages() == 4
        # All four pages share the SAME Helvetica clone -> a single identity.
        font_ids: set[int] = set()
        for page in result.get_pages():
            res = page.get_cos_object().get_dictionary_object(_n("Resources"))
            if res is None:
                continue
            fo = res.get_dictionary_object(_n("Font"))
            if fo is None:
                continue
            fd = fo.get_dictionary_object(_n("F1"))
            if fd is not None:
                font_ids.add(id(fd))
        assert len(font_ids) == 1
    finally:
        result.close()
