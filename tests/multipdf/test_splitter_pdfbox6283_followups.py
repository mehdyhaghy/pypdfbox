"""Hand-written tests for the PDFBOX-6283 ``Splitter`` follow-ups of the
PDFBox 3.0 branch (future 3.0.9): range validation in ``split()``, per
document id/role sets, no discarded clones in the struct dict map, no empty
``/IDTree``, cleanup on failure and per-run state reset.
"""

import logging

import pytest

from pypdfbox import PDDocument, PDPage
from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSInteger,
    COSName,
    COSNull,
    COSString,
)
from pypdfbox.multipdf import Splitter
from pypdfbox.pdmodel.documentinterchange.logicalstructure import (
    PDStructureTreeRoot,
)

_K = COSName.get_pdf_name("K")
_P = COSName.get_pdf_name("P")
_PG = COSName.get_pdf_name("Pg")
_S = COSName.get_pdf_name("S")
_ID = COSName.get_pdf_name("ID")
_TYPE = COSName.get_pdf_name("Type")
_MCID = COSName.get_pdf_name("MCID")
_NUMS = COSName.get_pdf_name("Nums")
_NAMES = COSName.get_pdf_name("Names")
_ROLE_MAP = COSName.get_pdf_name("RoleMap")
_ID_TREE = COSName.get_pdf_name("IDTree")
_PARENT_TREE = COSName.get_pdf_name("ParentTree")


def _make_doc(n_pages: int) -> PDDocument:
    doc = PDDocument()
    for _ in range(n_pages):
        doc.add_page(PDPage())
    return doc


def _element(
    role: str, page: PDPage | None, parent: COSDictionary, element_id: str | None
) -> COSDictionary:
    elem = COSDictionary()
    elem.set_item(_TYPE, COSName.get_pdf_name("StructElem"))
    elem.set_item(_S, COSName.get_pdf_name(role))
    elem.set_item(_P, parent)
    if page is not None:
        elem.set_item(_PG, page.get_cos_object())
    if element_id is not None:
        elem.set_string(_ID, element_id)
    return elem


def _mcr(page: PDPage, mcid: int) -> COSDictionary:
    mcr = COSDictionary()
    mcr.set_item(_TYPE, COSName.get_pdf_name("MCR"))
    mcr.set_item(_PG, page.get_cos_object())
    mcr.set_int(_MCID, mcid)
    return mcr


def _make_tagged_doc() -> tuple[PDDocument, COSDictionary]:
    """Two pages. ``kept`` is an element of page 0; ``dropped`` names page 1
    as /Pg but only holds an MCR of page 1, so it is dropped from the clone
    of chunk 0 after it was registered. Page 0's /ParentTree entry lists
    both."""
    doc = _make_doc(2)
    page0, page1 = doc.get_page(0), doc.get_page(1)
    page0.set_struct_parents(0)
    page1.set_struct_parents(1)

    root = PDStructureTreeRoot()
    root_dict = root.get_cos_object()
    kept = _element("P", page0, root_dict, "kept-id")
    kept.set_item(_K, COSInteger.get(0))
    dropped = _element("Span", page1, root_dict, "dropped-id")
    dropped_kids = COSArray()
    dropped_kids.add(_mcr(page1, 0))
    dropped.set_item(_K, dropped_kids)
    k = COSArray()
    k.add(kept)
    k.add(dropped)
    root_dict.set_item(_K, k)

    entry0 = COSArray()
    entry0.add(kept)
    entry0.add(dropped)
    entry1 = COSArray()
    entry1.add(dropped)
    nums = COSArray()
    nums.add(COSInteger.get(0))
    nums.add(entry0)
    nums.add(COSInteger.get(1))
    nums.add(entry1)
    parent_tree = COSDictionary()
    parent_tree.set_item(_NUMS, nums)
    root_dict.set_item(_PARENT_TREE, parent_tree)

    id_names = COSArray()
    for key, value in (("dropped-id", dropped), ("kept-id", kept)):
        id_names.add(COSString(key))
        id_names.add(value)
    id_tree = COSDictionary()
    id_tree.set_item(_NAMES, id_names)
    root_dict.set_item(_ID_TREE, id_tree)

    role_map = COSDictionary()
    role_map.set_item(COSName.get_pdf_name("P"), COSName.get_pdf_name("P"))
    role_map.set_item(COSName.get_pdf_name("Span"), COSName.get_pdf_name("Span"))
    root_dict.set_item(_ROLE_MAP, role_map)

    doc.get_document_catalog().set_struct_tree_root(root)
    return doc, dropped


def _struct_root(chunk: PDDocument) -> COSDictionary:
    root = chunk.get_document_catalog().get_struct_tree_root()
    assert root is not None
    return root.get_cos_object()


def _parent_tree_entry(root: COSDictionary, key: int) -> object:
    nums = root.get_dictionary_object(_PARENT_TREE).get_dictionary_object(_NUMS)
    for i in range(0, nums.size(), 2):
        if nums.get_object(i).int_value() == key:
            return nums.get_object(i + 1)
    return None


# ---------- range validation (3956ecc6) ----------


def test_end_before_start_is_rejected_by_split_in_any_setter_order() -> None:
    doc = _make_doc(3)
    try:
        splitter = Splitter().set_end_page(1).set_start_page(2)
        with pytest.raises(ValueError, match="End page is smaller than startPage"):
            splitter.split(doc)
        # the reverse order was rejected by set_end_page in 3.0.8; it is now
        # accepted there and rejected by split() as well
        splitter = Splitter().set_start_page(2).set_end_page(1)
        with pytest.raises(ValueError, match="End page is smaller than startPage"):
            splitter.split(doc)
    finally:
        doc.close()


def test_end_equal_to_start_is_a_single_page() -> None:
    doc = _make_doc(3)
    try:
        chunks = Splitter().set_start_page(2).set_end_page(2).split(doc)
        assert [chunk.get_number_of_pages() for chunk in chunks] == [1]
        for chunk in chunks:
            chunk.close()
    finally:
        doc.close()


# ---------- loop off-by-one (e15ac79c) ----------


def test_loop_stops_right_after_end_page() -> None:
    doc = _make_doc(5)
    seen: list[int] = []

    class Recording(Splitter):
        def split_at_page(self, page_number: int) -> bool:
            seen.append(page_number)
            return super().split_at_page(page_number)

    try:
        chunks = Recording().set_end_page(2).split(doc)
        assert [chunk.get_number_of_pages() for chunk in chunks] == [1, 1]
        assert seen == [0, 1]
        for chunk in chunks:
            chunk.close()
    finally:
        doc.close()


# ---------- per-document id / role sets (116a1529) ----------


def test_id_and_role_sets_are_reset_per_document() -> None:
    doc = _make_doc(2)
    page0, page1 = doc.get_page(0), doc.get_page(1)
    root = PDStructureTreeRoot()
    root_dict = root.get_cos_object()
    first = _element("H1", page0, root_dict, "first")
    second = _element("P", page1, root_dict, "second")
    k = COSArray()
    k.add(first)
    k.add(second)
    root_dict.set_item(_K, k)
    role_map = COSDictionary()
    role_map.set_item(COSName.get_pdf_name("H1"), COSName.get_pdf_name("H"))
    role_map.set_item(COSName.get_pdf_name("P"), COSName.get_pdf_name("P"))
    root_dict.set_item(_ROLE_MAP, role_map)
    id_names = COSArray()
    for key, value in (("first", first), ("second", second)):
        id_names.add(COSString(key))
        id_names.add(value)
    id_tree = COSDictionary()
    id_tree.set_item(_NAMES, id_names)
    root_dict.set_item(_ID_TREE, id_tree)
    doc.get_document_catalog().set_struct_tree_root(root)

    splitter = Splitter()
    chunks = splitter.split(doc)
    try:
        roles = [
            {key.get_name() for key in _struct_root(c).get_dictionary_object(
                _ROLE_MAP
            ).key_set()}
            for c in chunks
        ]
        assert roles == [{"H1"}, {"P"}]
        ids = []
        for chunk in chunks:
            names = (
                _struct_root(chunk)
                .get_dictionary_object(_ID_TREE)
                .get_dictionary_object(_NAMES)
            )
            ids.append(
                {names.get_object(i).get_string() for i in range(0, names.size(), 2)}
            )
        assert ids == [{"first"}, {"second"}]
    finally:
        for chunk in chunks:
            chunk.close()
        doc.close()


# ---------- no discarded clones in the struct dict map (696cd934, 9bf8a0b7,
# b8bc5592) ----------


@pytest.mark.parametrize("skip", [True, False], ids=["skip", "noskip"])
def test_discarded_clone_is_not_reached_through_parent_or_id_tree(
    skip: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    if not skip:
        monkeypatch.setattr(Splitter, "_build_k_skip_info", lambda self, k: None)
    doc, _ = _make_tagged_doc()
    chunks = Splitter().split(doc)
    try:
        assert len(chunks) == 2
        root0 = _struct_root(chunks[0])
        entry0 = _parent_tree_entry(root0, 0)
        assert isinstance(entry0, COSArray)
        assert entry0.size() == 2
        kept_clone = entry0.get_object(0)
        assert isinstance(kept_clone, COSDictionary)
        assert kept_clone.get_string(_ID) == "kept-id"
        # 3.0.8 put the half-built clone of "dropped" here
        assert entry0.get(1) is COSNull.NULL or entry0.get_object(1) is None
        names = root0.get_dictionary_object(_ID_TREE).get_dictionary_object(_NAMES)
        keys = [names.get_object(i).get_string() for i in range(0, names.size(), 2)]
        assert keys == ["kept-id"]
        # chunk 0 role map no longer carries the dropped element's role
        role_keys = {
            key.get_name()
            for key in root0.get_dictionary_object(_ROLE_MAP).key_set()
        }
        assert role_keys == {"P"}

        root1 = _struct_root(chunks[1])
        entry1 = _parent_tree_entry(root1, 1)
        assert isinstance(entry1, COSArray)
        dropped_clone = entry1.get_object(0)
        assert isinstance(dropped_clone, COSDictionary)
        assert dropped_clone.get_string(_ID) == "dropped-id"
    finally:
        for chunk in chunks:
            chunk.close()
        doc.close()


def test_discarded_clone_is_unregistered_by_the_k_cloner() -> None:
    page_dict = COSDictionary()
    other_page = COSDictionary()
    mcr = COSDictionary()
    mcr.set_item(_TYPE, COSName.get_pdf_name("MCR"))
    mcr.set_item(_PG, other_page)
    mcr.set_int(_MCID, 0)
    elem = COSDictionary()
    elem.set_item(_PG, other_page)
    elem.set_item(_K, mcr)
    splitter = Splitter()
    splitter._page_dict_map = {id(page_dict): COSDictionary()}
    assert splitter._k_create_clone(elem, COSDictionary(), None, None) is None
    assert splitter._struct_dict_map == {}


# ---------- empty /IDTree is not written (735e61bd) ----------


def test_no_id_tree_when_no_id_is_left() -> None:
    doc = _make_doc(2)
    page0, page1 = doc.get_page(0), doc.get_page(1)
    root = PDStructureTreeRoot()
    root_dict = root.get_cos_object()
    with_id = _element("P", page0, root_dict, "only-id")
    without_id = _element("P", page1, root_dict, None)
    k = COSArray()
    k.add(with_id)
    k.add(without_id)
    root_dict.set_item(_K, k)
    id_names = COSArray()
    id_names.add(COSString("only-id"))
    id_names.add(with_id)
    id_tree = COSDictionary()
    id_tree.set_item(_NAMES, id_names)
    root_dict.set_item(_ID_TREE, id_tree)
    doc.get_document_catalog().set_struct_tree_root(root)

    chunks = Splitter().split(doc)
    try:
        assert _struct_root(chunks[0]).contains_key(_ID_TREE)
        assert not _struct_root(chunks[1]).contains_key(_ID_TREE)
        # the /ParentTree is still always written
        assert _struct_root(chunks[1]).contains_key(_PARENT_TREE)
    finally:
        for chunk in chunks:
            chunk.close()
        doc.close()


# ---------- cleanup on failure (d6a68cee, 07594946, f4e84663, 892ca762) ----


def test_failure_in_process_page_closes_created_documents() -> None:
    created: list[PDDocument] = []

    class Failing(Splitter):
        def create_new_document(self) -> PDDocument:
            document = super().create_new_document()
            created.append(document)
            return document

        def process_page(self, page: PDPage) -> None:
            if self._current_page_number == 2:
                raise RuntimeError("not an OSError")
            super().process_page(page)

    doc = _make_doc(3)
    splitter = Failing()
    try:
        with pytest.raises(RuntimeError, match="not an OSError"):
            splitter.split(doc)
    finally:
        doc.close()
    assert len(created) == 2
    assert all(document.get_document().is_closed() for document in created)
    # per-run state is released
    assert splitter._destination_documents == []
    assert splitter._page_dict_maps == []
    assert splitter._current_destination_document is None


def test_successful_split_releases_per_run_state() -> None:
    doc = _make_doc(3)
    splitter = Splitter()
    chunks = splitter.split(doc)
    try:
        assert len(chunks) == 3
        assert all(not c.get_document().is_closed() for c in chunks)
        assert splitter._destination_documents == []
        assert splitter._page_dict_maps == []
        assert splitter._page_to_doc_num_map == {}
        assert splitter._annot_dict_maps == []
        assert splitter._dest_to_fix == []
        assert splitter._struct_dict_map == {}
        assert splitter._current_destination_document is None
    finally:
        for chunk in chunks:
            chunk.close()
        doc.close()


@pytest.mark.parametrize(
    "method",
    [
        "_clone_structure_tree",
        "_fix_destinations",
        "fix_name_destinations",
        "fix_name_destinations2",
    ],
)
def test_post_pass_failure_propagates_and_closes_documents(method: str) -> None:
    """Upstream ``split()`` lets a failed structure-tree clone, destination
    fix-up or named-destination fix-up escape; every created document is
    closed and nothing is returned."""
    created: list[PDDocument] = []

    def fail(*_args: object) -> None:
        raise OSError("broken post pass")

    class Failing(Splitter):
        def create_new_document(self) -> PDDocument:
            document = super().create_new_document()
            created.append(document)
            return document

    setattr(Failing, method, fail)

    doc = _make_doc(2)
    splitter = Failing()
    try:
        with pytest.raises(OSError, match="broken post pass"):
            splitter.split(doc)
    finally:
        doc.close()
    assert len(created) == 2
    assert all(document.get_document().is_closed() for document in created)
    assert splitter._destination_documents == []


def test_post_pass_failure_is_not_logged(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The failure is raised, not swallowed into an error log."""

    class Failing(Splitter):
        def clone_structure_tree(self, destination_document: PDDocument) -> None:
            raise OSError("broken tree")

        _clone_structure_tree = clone_structure_tree

    doc = _make_doc(2)
    try:
        with (
            caplog.at_level(logging.ERROR, logger="pypdfbox.multipdf.splitter"),
            pytest.raises(OSError, match="broken tree"),
        ):
            Failing().split(doc)
        assert "structure-tree clone failed" not in caplog.text
    finally:
        doc.close()


# ---------- reuse (6b6fad22) ----------


def test_reuse_with_a_different_split_length_starts_a_new_document() -> None:
    splitter = Splitter()
    doc = _make_doc(4)
    try:
        first = splitter.split(doc)
        assert [c.get_number_of_pages() for c in first] == [1, 1, 1, 1]
        splitter.set_split_at_page(3)
        second = splitter.split(doc)
        assert [c.get_number_of_pages() for c in second] == [3, 1]
        assert not set(map(id, first)) & set(map(id, second))
        for chunk in [*first, *second]:
            chunk.close()
    finally:
        doc.close()
