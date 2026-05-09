from __future__ import annotations

import logging

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName, COSString
from pypdfbox.multipdf.pdf_merger_utility import PDFMergerUtility
from pypdfbox.pdmodel.documentinterchange.logicalstructure import (
    PDStructureElementNumberTreeNode,
    PDStructureTreeRoot,
)

_NEXT = COSName.get_pdf_name("Next")
_NUMS = COSName.get_pdf_name("Nums")
_PAGE_LABELS = COSName.get_pdf_name("PageLabels")


class _IdentityCloner:
    def clone_for_new_document(self, value: object) -> object:
        return value


class _Catalog:
    def __init__(self, cos_object: COSDictionary | None = None) -> None:
        self._dict = cos_object if cos_object is not None else COSDictionary()
        self._outline: object | None = None
        self._struct_tree: object | None = None

    def get_cos_object(self) -> COSDictionary:
        return self._dict

    def get_document_outline(self) -> object | None:
        return self._outline

    def set_document_outline(self, outline: object) -> None:
        self._outline = outline

    def get_struct_tree_root(self) -> object | None:
        return self._struct_tree

    def set_struct_tree_root(self, tree: object) -> None:
        self._struct_tree = tree

    def get_pages(self) -> list[object]:
        return []


class _Document:
    def __init__(self, catalog: _Catalog, page_count: int = 0) -> None:
        self._catalog = catalog
        self._page_count = page_count

    def get_document_catalog(self) -> _Catalog:
        return self._catalog

    def get_number_of_pages(self) -> int:
        return self._page_count


class _OutlineItem:
    def __init__(self, next_item: object | None = None) -> None:
        self._dict = COSDictionary()
        self._next_item = next_item
        self.inserted: object | None = None

    def get_cos_object(self) -> COSDictionary:
        return self._dict

    def get_next_sibling(self) -> object | None:
        return self._next_item

    def insert_sibling_after(self, item: object) -> None:
        self.inserted = item


class _Outline:
    def __init__(self, first_child: object | None, children: list[object] | None = None) -> None:
        self._first_child = first_child
        self._children = children if children is not None else []

    def get_first_child(self) -> object | None:
        return self._first_child

    def children(self) -> list[object]:
        return self._children


class _CloseRaisesDocument:
    def __init__(self) -> None:
        self.saved_to: object | None = None

    def save(self, destination: object) -> None:
        self.saved_to = destination

    def close(self) -> None:
        raise RuntimeError("close failed")


def test_wave656_legacy_merge_logs_destination_close_errors(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    from pypdfbox.pdmodel import pd_document as pd_document_module

    source = object()
    util = PDFMergerUtility()
    util.add_source(source)  # type: ignore[arg-type]
    util.set_destination_stream(object())  # type: ignore[arg-type]
    monkeypatch.setattr(pd_document_module, "PDDocument", _CloseRaisesDocument)
    monkeypatch.setattr(
        PDFMergerUtility,
        "_open_source",
        staticmethod(lambda _source: (source, False)),
    )
    monkeypatch.setattr(util, "append_document", lambda _destination, _source: None)

    with caplog.at_level(logging.ERROR, logger="pypdfbox.multipdf.pdf_merger_utility"):
        util.merge_documents()

    assert "error closing destination PDDocument" in caplog.text


def test_wave656_merge_outline_ignores_cycles_and_stops_when_insert_yields_no_next(
    caplog: pytest.LogCaptureFixture,
) -> None:
    util = PDFMergerUtility()
    source_catalog = _Catalog()
    dest_catalog = _Catalog()
    child = _OutlineItem()
    source_catalog._outline = _Outline(None, [child])  # noqa: SLF001

    looping = _OutlineItem()
    looping._next_item = looping  # noqa: SLF001
    dest_catalog._outline = _Outline(looping)  # noqa: SLF001
    with caplog.at_level(logging.WARNING, logger="pypdfbox.multipdf.pdf_merger_utility"):
        util._merge_outline(_IdentityCloner(), source_catalog, dest_catalog)  # type: ignore[arg-type]  # noqa: SLF001,E501
    assert "Outline ignored" in caplog.text

    last = _OutlineItem()
    dest_catalog._outline = _Outline(last)  # noqa: SLF001
    util._merge_outline(_IdentityCloner(), source_catalog, dest_catalog)  # type: ignore[arg-type]  # noqa: SLF001,E501
    assert last.inserted is not None


def test_wave656_merge_page_labels_replaces_malformed_destination_nums() -> None:
    src_nums = COSArray([COSInteger.get(0), COSString("cover")])
    src_labels = COSDictionary()
    src_labels.set_item(_NUMS, src_nums)
    src_catalog_dict = COSDictionary()
    src_catalog_dict.set_item(_PAGE_LABELS, src_labels)

    dest_labels = COSDictionary()
    dest_labels.set_item(_NUMS, COSDictionary())
    dest_catalog_dict = COSDictionary()
    dest_catalog_dict.set_item(_PAGE_LABELS, dest_labels)

    PDFMergerUtility()._merge_page_labels(  # type: ignore[arg-type]  # noqa: SLF001
        _IdentityCloner(),
        _Document(_Catalog(src_catalog_dict)),
        _Document(_Catalog(dest_catalog_dict), page_count=4),
    )

    dest_nums = dest_labels.get_dictionary_object(_NUMS)
    assert isinstance(dest_nums, COSArray)
    assert dest_nums.get_object(0) == COSInteger.get(4)
    assert dest_nums.get_object(1) == COSString("cover")


def test_wave656_prepare_struct_tree_merge_derives_negative_next_key_from_dest_map() -> None:
    src_root = PDStructureTreeRoot()
    src_parent_tree = PDStructureElementNumberTreeNode()
    src_parent_tree.set_numbers({0: COSDictionary()})
    src_root.set_parent_tree(src_parent_tree)

    dest_root = PDStructureTreeRoot()
    dest_parent_tree = PDStructureElementNumberTreeNode()
    dest_parent_tree.set_numbers({2: COSDictionary(), 8: COSDictionary()})
    dest_root.set_parent_tree(dest_parent_tree)
    dest_root.set_parent_tree_next_key(-1)

    src_catalog = _Catalog()
    src_catalog._struct_tree = src_root  # noqa: SLF001
    dest_catalog = _Catalog()
    dest_catalog._struct_tree = dest_root  # noqa: SLF001

    result = PDFMergerUtility()._prepare_struct_tree_merge(  # type: ignore[arg-type]  # noqa: SLF001,E501
        src_catalog,
        dest_catalog,
        _Document(dest_catalog),
    )

    merge_struct_tree, next_key, src_map, dest_map, _, _ = result
    assert merge_struct_tree is True
    assert next_key == 9
    assert set(src_map) == {0}
    assert set(dest_map) == {2, 8}
