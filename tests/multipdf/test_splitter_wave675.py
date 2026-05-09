from __future__ import annotations

from typing import Any

import pytest

from pypdfbox.cos import COSDictionary, COSInteger, COSName
from pypdfbox.multipdf import Splitter
from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_structure_tree_root import (
    PDStructureElementNumberTreeNode,
)

_K = COSName.get_pdf_name("K")
_PG = COSName.get_pdf_name("Pg")


class _SourceStructRoot:
    def __init__(
        self,
        root_dict: COSDictionary,
        parent_tree: object | None,
    ) -> None:
        self._dict = root_dict
        self._parent_tree = parent_tree

    def get_cos_object(self) -> COSDictionary:
        return self._dict

    def get_parent_tree(self) -> object | None:
        return self._parent_tree

    def get_id_tree(self) -> None:
        return None


class _SourceCatalog:
    def __init__(self, root: _SourceStructRoot) -> None:
        self._root = root

    def get_struct_tree_root(self) -> _SourceStructRoot:
        return self._root


class _SourceDocument:
    def __init__(self, root: _SourceStructRoot) -> None:
        self._catalog = _SourceCatalog(root)

    def get_document_catalog(self) -> _SourceCatalog:
        return self._catalog


class _NumberTree:
    def __init__(self, numbers: dict[int, COSDictionary]) -> None:
        self._numbers = numbers

    def get_numbers(self) -> dict[int, COSDictionary]:
        return self._numbers

    def get_kids(self) -> None:
        return None


class _DestinationPage:
    def __init__(self, struct_parent: int) -> None:
        self._struct_parent = struct_parent

    def get_struct_parents(self) -> int:
        return self._struct_parent

    def get_annotations(self) -> list[object]:
        return []


class _DestinationPages:
    def __init__(
        self,
        page: _DestinationPage,
        retained_page_dict: COSDictionary,
    ) -> None:
        self._page = page
        self._retained_page_dict = retained_page_dict

    def __len__(self) -> int:
        return 1

    def get(self, index: int) -> _DestinationPage:
        assert index == 0
        return self._page

    def index_of(self, page_dict: COSDictionary) -> int:
        return 0 if page_dict is self._retained_page_dict else -1


class _DestinationCatalog:
    def __init__(self) -> None:
        self.struct_root: Any | None = None

    def set_struct_tree_root(self, root: object) -> None:
        self.struct_root = root


class _DestinationDocument:
    def __init__(
        self,
        page: _DestinationPage,
        retained_page_dict: COSDictionary,
    ) -> None:
        self._pages = _DestinationPages(page, retained_page_dict)
        self._catalog = _DestinationCatalog()

    def get_pages(self) -> _DestinationPages:
        return self._pages

    def get_document_catalog(self) -> _DestinationCatalog:
        return self._catalog


def test_wave675_clone_structure_tree_sets_parent_tree_next_key_for_retained_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        PDStructureElementNumberTreeNode,
        "get_upper_limit",
        lambda self: 0,
    )
    source_page = COSDictionary()
    cloned_page = COSDictionary()
    retained_element = COSDictionary()
    retained_element.set_item(_PG, source_page)
    retained_element.set_item(_K, COSInteger.get(0))

    root_dict = COSDictionary()
    root_dict.set_item(_K, retained_element)
    source_root = _SourceStructRoot(root_dict, _NumberTree({0: retained_element}))

    destination_page = _DestinationPage(struct_parent=0)
    destination = _DestinationDocument(destination_page, cloned_page)
    splitter = Splitter()
    splitter._source_document = _SourceDocument(source_root)  # type: ignore[assignment]  # noqa: SLF001,E501
    splitter._page_dict_map = {id(source_page): cloned_page}  # noqa: SLF001

    splitter._clone_structure_tree(destination)  # type: ignore[arg-type]  # noqa: SLF001

    assert destination.get_document_catalog().struct_root is not None
    assert (
        destination.get_document_catalog()
        .struct_root.get_parent_tree_next_key()
        == 1
    )
