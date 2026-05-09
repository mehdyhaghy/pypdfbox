from __future__ import annotations

from typing import Any

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName
from pypdfbox.multipdf import Splitter
from pypdfbox.pdmodel.interactive.documentnavigation.destination import (
    PDPageDestination,
)

_ANNOTS = COSName.get_pdf_name("Annots")
_CLASS_MAP = COSName.get_pdf_name("ClassMap")
_ID = COSName.get_pdf_name("ID")
_K = COSName.get_pdf_name("K")
_OBJ = COSName.get_pdf_name("Obj")
_P = COSName.get_pdf_name("P")
_PG = COSName.get_pdf_name("Pg")
_ROLE_MAP = COSName.get_pdf_name("RoleMap")
_S = COSName.get_pdf_name("S")
_SUBTYPE = COSName.get_pdf_name("Subtype")
_TYPE = COSName.get_pdf_name("Type")


class _PageTree:
    def __init__(self, index: int = 0) -> None:
        self.index = index

    def index_of(self, page_dict: COSDictionary) -> int:
        return self.index


class _Root:
    def __init__(self, root_dict: COSDictionary | None = None) -> None:
        self._dict = root_dict if root_dict is not None else COSDictionary()
        self.id_tree: object | None = None
        self.parent_tree: object | None = None

    def get_cos_object(self) -> COSDictionary:
        return self._dict

    def get_parent_tree(self) -> object | None:
        return self.parent_tree

    def get_id_tree(self) -> object | None:
        return self.id_tree

    def set_id_tree(self, tree: object) -> None:
        self.id_tree = tree


class _IdentityNameTree:
    def __init__(self) -> None:
        self.names: dict[str, object] = {}

    def set_names(self, names: dict[str, object]) -> None:
        self.names = names


def test_wave654_process_page_tolerates_resource_read_and_write_failures() -> None:
    class ImportedPage:
        def __init__(self) -> None:
            self._dict = COSDictionary()

        def get_cos_object(self) -> COSDictionary:
            return self._dict

        def get_annotations(self) -> list[object]:
            return []

        def set_resources(self, resources: object) -> None:
            raise OSError("cannot copy resources")

    class DestinationDocument:
        def __init__(self, imported: ImportedPage) -> None:
            self.imported = imported

        def import_page(self, page: object) -> ImportedPage:
            return self.imported

    class ResourceFailingPage:
        def __init__(self) -> None:
            self._dict = COSDictionary()

        def get_resources(self) -> object:
            raise OSError("cannot read resources")

        def get_cos_object(self) -> COSDictionary:
            return self._dict

    class ResourceWriteFailingPage(ResourceFailingPage):
        def get_resources(self) -> object:
            return object()

    class TestSplitter(Splitter):
        def __init__(self, imported: ImportedPage) -> None:
            super().__init__()
            self.imported = imported

        def create_new_document(self) -> DestinationDocument:
            return DestinationDocument(self.imported)

    TestSplitter(ImportedPage()).process_page(ResourceFailingPage())  # type: ignore[arg-type]
    TestSplitter(ImportedPage()).process_page(ResourceWriteFailingPage())  # type: ignore[arg-type]


def test_wave654_signature_widget_returns_false_when_subtype_lookup_fails() -> None:
    class BrokenAnnotation:
        def get_name(self, key: COSName) -> str | None:
            raise AttributeError("no names")

    assert not Splitter._is_signature_widget(BrokenAnnotation())  # type: ignore[arg-type]  # noqa: SLF001,E501


def test_wave654_stage_link_destination_ignores_non_array_page_destination() -> None:
    class NonArrayDestination(PDPageDestination):
        def get_cos_object(self) -> COSDictionary:
            return COSDictionary()

    class Link:
        def get_destination(self) -> PDPageDestination:
            return NonArrayDestination()

    splitter = Splitter()

    splitter._stage_link_destination(Link(), COSDictionary())  # type: ignore[arg-type]  # noqa: SLF001,E501

    assert splitter._dest_to_fix == []  # noqa: SLF001


def test_wave654_stage_link_destination_ignores_uncreatable_destination() -> None:
    class ShortArrayDestination(PDPageDestination):
        def __init__(self) -> None:
            self._array = COSArray()
            self._array.add(COSDictionary())

        def get_cos_object(self) -> COSArray:
            return self._array

    class Link:
        def get_destination(self) -> PDPageDestination:
            return ShortArrayDestination()

    splitter = Splitter()

    splitter._stage_link_destination(Link(), COSDictionary())  # type: ignore[arg-type]  # noqa: SLF001,E501

    assert splitter._dest_to_fix == []  # noqa: SLF001


def test_wave654_clone_structure_tree_tolerates_bad_page_and_annotation_state() -> None:
    class BadAnnotation:
        def get_struct_parent(self) -> int:
            raise OSError("bad annotation")

    class BadStructParentPage:
        def get_struct_parents(self) -> int:
            raise OSError("bad page")

        def get_annotations(self) -> list[BadAnnotation]:
            return [BadAnnotation()]

    class BadAnnotationsPage:
        def get_struct_parents(self) -> int:
            return -1

        def get_annotations(self) -> list[object]:
            raise OSError("bad annotations")

    class DestinationPages:
        def __init__(self) -> None:
            self.pages = [BadStructParentPage(), BadAnnotationsPage()]

        def __len__(self) -> int:
            return len(self.pages)

        def get(self, index: int) -> object:
            return self.pages[index]

        def index_of(self, page_dict: COSDictionary) -> int:
            return -1

    class SourceCatalog:
        def __init__(self, root: _Root) -> None:
            self.root = root

        def get_struct_tree_root(self) -> _Root:
            return self.root

    class SourceDocument:
        def __init__(self, root: _Root) -> None:
            self.catalog = SourceCatalog(root)

        def get_document_catalog(self) -> SourceCatalog:
            return self.catalog

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

    source_root_dict = COSDictionary()
    class_map = COSDictionary()
    source_root_dict.set_item(_CLASS_MAP, class_map)
    splitter = Splitter()
    splitter._source_document = SourceDocument(_Root(source_root_dict))  # type: ignore[assignment]  # noqa: SLF001,E501
    destination = DestinationDocument()
    assert destination.pages.index_of(COSDictionary()) == -1

    splitter._clone_structure_tree(destination)  # type: ignore[arg-type]  # noqa: SLF001

    assert destination.catalog.root is not None
    cloned_root = destination.catalog.root.get_cos_object()
    assert cloned_root.get_dictionary_object(_CLASS_MAP) is class_map


def test_wave654_k_clone_drops_page_reference_not_in_destination_tree() -> None:
    source_page = COSDictionary()
    cloned_page = COSDictionary()
    src = COSDictionary()
    src.set_item(_PG, source_page)
    splitter = Splitter()
    splitter._page_dict_map = {id(source_page): cloned_page}  # noqa: SLF001

    assert (
        splitter._k_create_clone(src, COSDictionary(), None, _PageTree(index=-1))  # noqa: SLF001,E501
        is None
    )


def test_wave654_k_clone_drops_parent_when_all_kids_are_dropped() -> None:
    child = COSDictionary()
    child.set_item(_TYPE, COSName.get_pdf_name("MCR"))
    child.set_item(_K, COSInteger.get(0))
    src = COSDictionary()
    src.set_item(_K, child)

    assert (
        Splitter()._k_create_clone(src, COSDictionary(), COSDictionary(), _PageTree())  # noqa: SLF001,E501
        is None
    )


def test_wave654_remove_possible_orphan_annotation_keeps_obj_without_host_page() -> None:
    source_annotation = COSDictionary()
    source_annotation.set_item(_SUBTYPE, COSName.get_pdf_name("Link"))
    dst = COSDictionary()
    dst.set_item(_OBJ, source_annotation)

    Splitter()._remove_possible_orphan_annotation(  # noqa: SLF001
        source_annotation, COSDictionary(), None, dst
    )

    assert dst.get_dictionary_object(_OBJ) is source_annotation


def test_wave654_clone_role_map_noops_without_source_role_map() -> None:
    destination = _Root()

    Splitter()._clone_role_map(_Root(), destination)  # noqa: SLF001

    assert not destination.get_cos_object().contains_key(_ROLE_MAP)


def test_wave654_clone_id_tree_noops_for_missing_empty_and_unretained_names() -> None:
    class EmptyTree:
        def get_names(self) -> dict[str, object]:
            return {}

        def get_kids(self) -> None:
            return None

    class UnretainedTree:
        def get_names(self) -> dict[str, COSDictionary]:
            return {"drop": COSDictionary()}

        def get_kids(self) -> None:
            return None

    destination = _Root()
    splitter = Splitter()
    splitter._clone_id_tree(_Root(), destination, _IdentityNameTree)  # noqa: SLF001
    assert destination.id_tree is None

    source = _Root()
    source.id_tree = EmptyTree()
    splitter._clone_id_tree(source, destination, _IdentityNameTree)  # noqa: SLF001
    assert destination.id_tree is None

    source.id_tree = UnretainedTree()
    assert source.id_tree.get_kids() is None
    splitter._id_set = {"keep"}  # noqa: SLF001
    splitter._clone_id_tree(source, destination, _IdentityNameTree)  # noqa: SLF001
    assert destination.id_tree is None


def test_wave654_k_clone_tracks_id_and_role_on_retained_child() -> None:
    source_page = COSDictionary()
    cloned_page = COSDictionary()
    child = COSDictionary()
    child.set_item(_PG, source_page)
    child.set_string(_ID, "child-id")
    child.set_item(_S, COSName.get_pdf_name("P"))
    src = COSDictionary()
    src.set_item(_K, child)
    splitter = Splitter()
    splitter._page_dict_map = {id(source_page): cloned_page}  # noqa: SLF001

    cloned = splitter._k_create_clone(src, COSDictionary(), None, _PageTree())  # noqa: SLF001

    assert isinstance(cloned, COSDictionary)
    assert splitter._id_set == {"child-id"}  # noqa: SLF001
    assert splitter._role_set == {"P"}  # noqa: SLF001
    assert isinstance(cloned.get_dictionary_object(_K), COSDictionary)
