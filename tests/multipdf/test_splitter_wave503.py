from __future__ import annotations

import logging

import pytest

from pypdfbox import PDDocument, PDPage
from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName, COSObject
from pypdfbox.multipdf import Splitter
from pypdfbox.pdmodel.pd_document_information import PDDocumentInformation

_ANNOTS = COSName.get_pdf_name("Annots")
_BYTE_RANGE = COSName.get_pdf_name("ByteRange")
_ID = COSName.get_pdf_name("ID")
_K = COSName.get_pdf_name("K")
_OBJ = COSName.get_pdf_name("Obj")
_P = COSName.get_pdf_name("P")
_PG = COSName.get_pdf_name("Pg")
_ROLE_MAP = COSName.get_pdf_name("RoleMap")
_S = COSName.get_pdf_name("S")
_SUBTYPE = COSName.get_pdf_name("Subtype")
_TYPE = COSName.get_pdf_name("Type")
_V = COSName.get_pdf_name("V")


class _IdentityNameTree:
    def __init__(self) -> None:
        self.names: dict[str, object] = {}

    def set_names(self, names: dict[str, object]) -> None:
        self.names = names


class _Root:
    def __init__(self, root_dict: COSDictionary) -> None:
        self._dict = root_dict
        self.id_tree: object | None = None

    def get_cos_object(self) -> COSDictionary:
        return self._dict

    def get_id_tree(self) -> object | None:
        return self.id_tree

    def set_id_tree(self, tree: object) -> None:
        self.id_tree = tree


def _make_doc(page_count: int) -> PDDocument:
    doc = PDDocument()
    for _ in range(page_count):
        doc.add_page(PDPage())
    return doc


def test_wave503_create_new_document_warns_when_root_and_info_share_dict(
    caplog: pytest.LogCaptureFixture,
) -> None:
    source = _make_doc(1)
    root_dict = source.get_document_catalog().get_cos_object()
    root_dict.set_item(COSName.get_pdf_name("NestedInfo"), COSDictionary())
    source.set_document_information(PDDocumentInformation(root_dict))

    with caplog.at_level(logging.WARNING, logger="pypdfbox.multipdf.splitter"):
        chunks = Splitter().split(source)

    assert "/Root and /Info share the same dictionary" in caplog.text
    chunks[0].close()
    source.close()


def test_wave503_process_annotations_returns_when_annotation_read_fails() -> None:
    class BrokenImportedPage:
        def get_annotations(self) -> object:
            raise OSError("bad annotations")

    Splitter()._process_annotations(PDPage(), BrokenImportedPage())  # type: ignore[arg-type]  # noqa: SLF001,E501


def test_wave503_signature_widget_detects_signature_value_type() -> None:
    widget = COSDictionary()
    widget.set_item(_SUBTYPE, COSName.get_pdf_name("Widget"))
    signature_value = COSDictionary()
    signature_value.set_item(_TYPE, COSName.get_pdf_name("Sig"))
    widget.set_item(_V, signature_value)

    assert Splitter._is_signature_widget(widget)  # noqa: SLF001


def test_wave503_stage_link_destination_ignores_links_with_broken_action() -> None:
    class LinkWithBrokenAction:
        def get_destination(self) -> None:
            return None

        def get_action(self) -> object:
            raise OSError("bad action")

    splitter = Splitter()

    splitter._stage_link_destination(LinkWithBrokenAction(), COSDictionary())  # type: ignore[arg-type]  # noqa: SLF001,E501

    assert splitter._dest_to_fix == []  # noqa: SLF001


def test_wave503_k_clone_dictionary_reuses_existing_clone_and_tracks_id_role() -> None:
    class PageTree:
        def index_of(self, page_dict: COSDictionary) -> int:
            return 0

    splitter = Splitter()
    parent = COSDictionary()
    src = COSDictionary()
    src.set_string(_ID, "kept-id")
    src.set_item(_S, COSName.get_pdf_name("P"))

    first = splitter._k_create_clone(src, parent, parent, PageTree())  # noqa: SLF001
    second = splitter._k_create_clone(src, parent, parent, PageTree())  # noqa: SLF001

    assert first is second
    assert splitter._id_set == {"kept-id"}  # noqa: SLF001
    assert splitter._role_set == {"P"}  # noqa: SLF001
    assert first.get_dictionary_object(_P) is parent


def test_wave503_k_clone_drops_unmapped_page_mcid_and_rootless_mcr() -> None:
    class PageTree:
        def index_of(self, page_dict: COSDictionary) -> int:
            return -1

    splitter = Splitter()
    missing_page = COSDictionary()
    mcr_with_missing_page = COSDictionary()
    mcr_with_missing_page.set_item(_TYPE, COSName.get_pdf_name("MCR"))
    mcr_with_missing_page.set_item(_PG, missing_page)
    mcr_with_missing_page.set_item(_K, COSInteger.get(0))

    assert (
        splitter._k_create_clone(  # noqa: SLF001
            mcr_with_missing_page, COSDictionary(), None, PageTree()
        )
        is None
    )

    rootless_mcr = COSDictionary()
    rootless_mcr.set_item(_TYPE, COSName.get_pdf_name("MCR"))
    assert (
        splitter._k_create_clone(rootless_mcr, COSDictionary(), None, PageTree())  # noqa: SLF001,E501
        is None
    )


def test_wave503_objr_rewrites_cloned_annotation_reference() -> None:
    class PageTree:
        def index_of(self, page_dict: COSDictionary) -> int:
            return 0

    source_page = COSDictionary()
    cloned_page = COSDictionary()
    source_annotation = COSDictionary()
    cloned_annotation = COSDictionary()
    splitter = Splitter()
    splitter._page_dict_map = {id(source_page): cloned_page}  # noqa: SLF001
    splitter._annot_dict_map = {id(source_annotation): cloned_annotation}  # noqa: SLF001

    objr = COSDictionary()
    objr.set_item(_TYPE, COSName.get_pdf_name("OBJR"))
    objr.set_item(_PG, source_page)
    objr.set_item(_OBJ, source_annotation)

    cloned = splitter._k_create_clone(objr, COSDictionary(), None, PageTree())  # noqa: SLF001

    assert isinstance(cloned, COSDictionary)
    assert cloned.get_dictionary_object(_PG) is cloned_page
    assert cloned.get_dictionary_object(_OBJ) is cloned_annotation


def test_wave503_orphan_annotation_keeps_object_when_present_on_current_page() -> None:
    splitter = Splitter()
    source_annotation = COSDictionary()
    source_annotation.set_item(_SUBTYPE, COSName.get_pdf_name("Link"))
    current_page = COSDictionary()
    annots = COSArray()
    annots.add(source_annotation)
    current_page.set_item(_ANNOTS, annots)
    dst = COSDictionary()
    dst.set_item(_OBJ, source_annotation)

    splitter._remove_possible_orphan_annotation(  # noqa: SLF001
        source_annotation, COSDictionary(), current_page, dst
    )

    assert dst.get_dictionary_object(_OBJ) is source_annotation


def test_wave503_role_map_and_id_tree_are_filtered_to_retained_structure() -> None:
    source_struct = COSDictionary()
    source_struct.set_string(_ID, "keep")
    source_role_map = COSDictionary()
    source_role_map.set_item(COSName.get_pdf_name("P"), COSName.get_pdf_name("Paragraph"))
    source_role_map.set_item(COSName.get_pdf_name("H1"), COSName.get_pdf_name("Heading"))
    source_root_dict = COSDictionary()
    source_root_dict.set_item(_ROLE_MAP, source_role_map)
    source_root = _Root(source_root_dict)

    class IdTree:
        def get_names(self) -> dict[str, COSDictionary]:
            return {"keep": source_struct, "drop": COSDictionary()}

        def get_kids(self) -> None:
            return None

    source_root.id_tree = IdTree()
    dest_root = _Root(COSDictionary())
    cloned_struct = COSDictionary()
    splitter = Splitter()
    splitter._role_set = {"P"}  # noqa: SLF001
    splitter._id_set = {"keep"}  # noqa: SLF001
    splitter._struct_dict_map = {id(source_struct): cloned_struct}  # noqa: SLF001

    splitter._clone_role_map(source_root, dest_root)  # noqa: SLF001
    splitter._clone_id_tree(source_root, dest_root, _IdentityNameTree)  # noqa: SLF001

    cloned_role_map = dest_root.get_cos_object().get_dictionary_object(_ROLE_MAP)
    assert isinstance(cloned_role_map, COSDictionary)
    assert cloned_role_map.contains_key(COSName.get_pdf_name("P"))
    assert not cloned_role_map.contains_key(COSName.get_pdf_name("H1"))
    assert isinstance(dest_root.id_tree, _IdentityNameTree)
    assert list(dest_root.id_tree.names) == ["keep"]


def test_wave503_has_mcids_finds_integer_inside_array_and_object_array_clone() -> None:
    splitter = Splitter()
    child = COSDictionary()
    wrapped = COSObject(12, resolved=child)
    src = COSArray()
    src.add(wrapped)

    cloned = splitter._k_clone_array(src, COSDictionary(), COSDictionary(), object())  # noqa: SLF001,E501

    assert isinstance(cloned, COSArray)
    assert cloned.get_object(0) is not child
    mcids = COSArray()
    mcids.add(COSName.get_pdf_name("NotAnInteger"))
    mcids.add(COSInteger.get(4))
    assert Splitter._has_mcids(mcids)  # noqa: SLF001
