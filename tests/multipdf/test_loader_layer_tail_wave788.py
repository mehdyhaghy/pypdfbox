from __future__ import annotations

from typing import Any

import pytest

from pypdfbox import Loader, PDDocument
from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.multipdf import PageExtractor, Splitter
from pypdfbox.multipdf.layer_utility import _at_quadrant_rotate, _coerce_matrix
from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_structure_tree_root import (  # noqa: E501
    PDStructureElementNumberTreeNode,
)

_K = COSName.get_pdf_name("K")
_OBJ = COSName.get_pdf_name("Obj")
_PG = COSName.get_pdf_name("Pg")
_TYPE = COSName.get_pdf_name("Type")


def test_wave788_loader_explicit_entry_points_reject_wrong_source_types() -> None:
    with pytest.raises(TypeError, match="expected bytes"):
        Loader.load_pdf_from_bytes("not-bytes")  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="expected str or PathLike"):
        Loader.load_pdf_from_file(b"not-a-path")  # type: ignore[arg-type]


def test_wave788_page_extractor_mutable_bounds_can_select_empty_range() -> None:
    source = PDDocument()
    try:
        extractor = PageExtractor(source, 1, 1)
        extractor.set_start_page(3)
        extractor.set_end_page(2)

        extracted = extractor.extract()
        try:
            assert extracted.get_number_of_pages() == 0
        finally:
            extracted.close()
    finally:
        source.close()


def test_wave788_layer_matrix_helpers_cover_identity_rotation_and_float_coercion() -> None:
    matrix = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]

    assert _at_quadrant_rotate(matrix, 4) == matrix
    assert _coerce_matrix((1, 0, 0, 1, 2, 3)) == [1.0, 0.0, 0.0, 1.0, 2.0, 3.0]


def test_wave788_splitter_parent_tree_keeps_annotation_struct_parent() -> None:
    source_page = COSDictionary()
    cloned_page = COSDictionary()
    source_annotation = COSDictionary()
    cloned_annotation = COSDictionary()

    objr = COSDictionary()
    objr.set_item(_TYPE, COSName.get_pdf_name("OBJR"))
    objr.set_item(_PG, source_page)
    objr.set_item(_OBJ, source_annotation)

    root_dict = COSDictionary()
    root_dict.set_item(_K, objr)
    parent_tree = PDStructureElementNumberTreeNode(COSDictionary())
    parent_tree.set_numbers({7: objr})

    class SourceRoot:
        def get_cos_object(self) -> COSDictionary:
            return root_dict

        def get_parent_tree(self) -> PDStructureElementNumberTreeNode:
            return parent_tree

        def get_id_tree(self) -> None:
            return None

    class SourceCatalog:
        def get_struct_tree_root(self) -> SourceRoot:
            return SourceRoot()

    class SourceDocument:
        def get_document_catalog(self) -> SourceCatalog:
            return SourceCatalog()

    class Annotation:
        def get_struct_parent(self) -> int:
            return 7

    class Page:
        def get_struct_parents(self) -> int:
            return -1

        def get_annotations(self) -> list[Annotation]:
            return [Annotation()]

    class DestinationPages:
        def __len__(self) -> int:
            return 1

        def get(self, index: int) -> Page:
            assert index == 0
            return Page()

        def index_of(self, page_dict: COSDictionary) -> int:
            return 0 if page_dict is cloned_page else -1

    class DestinationCatalog:
        def __init__(self) -> None:
            self.root: Any | None = None

        def set_struct_tree_root(self, root: object) -> None:
            self.root = root

    class DestinationDocument:
        def __init__(self) -> None:
            self.catalog = DestinationCatalog()
            self.pages = DestinationPages()

        def get_pages(self) -> DestinationPages:
            return self.pages

        def get_document_catalog(self) -> DestinationCatalog:
            return self.catalog

    splitter = Splitter()
    splitter._source_document = SourceDocument()  # type: ignore[assignment]  # noqa: SLF001
    splitter._page_dict_map = {id(source_page): cloned_page}  # noqa: SLF001
    splitter._annot_dict_map = {id(source_annotation): cloned_annotation}  # noqa: SLF001
    destination = DestinationDocument()

    splitter._clone_structure_tree(destination)  # type: ignore[arg-type]  # noqa: SLF001

    assert destination.catalog.root is not None
    numbers = destination.catalog.root.get_parent_tree().get_numbers()
    retained_objr = numbers[7]
    assert retained_objr.get_dictionary_object(_PG) is cloned_page
    assert retained_objr.get_dictionary_object(_OBJ) is cloned_annotation
