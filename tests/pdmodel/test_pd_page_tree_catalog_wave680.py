from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName, COSObject
from pypdfbox.pdmodel import PDDocument, PDDocumentCatalog, PDPage, PDPageTree
from pypdfbox.pdmodel.documentinterchange.logicalstructure import PDMarkInfo


def _name(value: str) -> COSName:
    return COSName.get_pdf_name(value)


def _page_dict() -> COSDictionary:
    page = COSDictionary()
    page.set_item(COSName.TYPE, COSName.PAGE)  # type: ignore[attr-defined]
    return page


def test_page_tree_root_document_accessors_and_negative_count_len() -> None:
    root = COSDictionary()
    root.set_item(COSName.TYPE, COSName.PAGES)  # type: ignore[attr-defined]
    kids = COSArray()
    kids.add(_page_dict())
    root.set_item(_name("Kids"), kids)
    root.set_item(_name("Count"), COSInteger(-1))

    with PDDocument() as doc:
        tree = PDPageTree(root, document=doc)

        assert tree.get_root() is root
        assert tree.get_document() is doc
        assert len(tree) == 1


def test_page_tree_iteration_ignores_cycles() -> None:
    root = COSDictionary()
    root.set_item(COSName.TYPE, COSName.PAGES)  # type: ignore[attr-defined]
    kids = COSArray()
    kids.add(root)
    root.set_item(_name("Kids"), kids)
    root.set_int(_name("Count"), 0)

    assert list(PDPageTree(root).iterator()) == []


def test_page_tree_remove_returns_false_when_declared_parent_has_no_kids() -> None:
    parent = COSDictionary()
    page = _page_dict()
    page.set_item(_name("Parent"), parent)

    assert PDPageTree().remove(PDPage(page)) is False


def test_page_tree_insert_before_and_after_use_root_for_parentless_target() -> None:
    for insert_name in ("insert_before", "insert_after"):
        tree = PDPageTree()
        root = tree.get_root()
        target = _page_dict()
        kids = root.get_dictionary_object(_name("Kids"))
        assert isinstance(kids, COSArray)
        kids.add(target)
        root.set_int(_name("Count"), 1)

        getattr(tree, insert_name)(PDPage(), PDPage(target))

        assert len(tree) == 2


def test_page_tree_insert_errors_for_missing_or_mismatched_parent_kids() -> None:
    target_without_kids = _page_dict()
    target_without_kids.set_item(_name("Parent"), COSDictionary())

    with pytest.raises(ValueError, match="no /Kids parent array"):
        PDPageTree().insert_before(PDPage(), PDPage(target_without_kids))

    parent = COSDictionary()
    parent.set_item(_name("Kids"), COSArray())
    target_not_in_kids = _page_dict()
    target_not_in_kids.set_item(_name("Parent"), parent)

    with pytest.raises(ValueError, match="not in its declared parent's /Kids"):
        PDPageTree().insert_after(PDPage(), PDPage(target_not_in_kids))


def test_page_tree_add_repairs_missing_root_kids_and_remove_finds_indirect_kid() -> None:
    root = COSDictionary()
    root.set_item(COSName.TYPE, COSName.PAGES)  # type: ignore[attr-defined]
    root.set_int(_name("Count"), 0)
    tree = PDPageTree(root)

    tree.add(PDPage())

    assert isinstance(root.get_dictionary_object(_name("Kids")), COSArray)
    assert len(tree) == 1

    indirect_page = _page_dict()
    indirect_page.set_item(_name("Parent"), root)
    kids = root.get_dictionary_object(_name("Kids"))
    assert isinstance(kids, COSArray)
    kids.clear()
    kids.add(COSObject(7, resolved=indirect_page))
    root.set_int(_name("Count"), 1)

    assert tree.remove(PDPage(indirect_page)) is True
    assert len(tree) == 0


def test_catalog_mark_info_setters_materialize_and_accept_wrapper() -> None:
    with PDDocument() as doc:
        catalog = doc.get_document_catalog()
        mark_info = PDMarkInfo()
        mark_info.set_marked(True)

        catalog.set_mark_info(mark_info)

        assert catalog.get_mark_info().get_cos_object() is mark_info.get_cos_object()

    with PDDocument() as doc:
        catalog = doc.get_document_catalog()

        catalog.set_user_properties(True)

        assert catalog.has_mark_info() is True
        assert catalog.has_user_properties() is True

    with PDDocument() as doc:
        catalog = doc.get_document_catalog()

        catalog.set_suspects(True)

        assert catalog.has_mark_info() is True
        assert catalog.has_suspects() is True


def test_catalog_set_actions_accepts_wrapper_object() -> None:
    class _Actions:
        def __init__(self) -> None:
            self.cos = COSDictionary()

        def get_cos_object(self) -> COSDictionary:
            return self.cos

    with PDDocument() as doc:
        catalog = doc.get_document_catalog()
        actions = _Actions()

        catalog.set_actions(actions)

        assert catalog.get_cos_object().get_dictionary_object(_name("AA")) is actions.cos


def test_catalog_set_oc_properties_tolerates_document_version_failure() -> None:
    catalog = PDDocumentCatalog(None, COSDictionary())  # type: ignore[arg-type]
    raw_oc_properties = COSDictionary()

    catalog.set_oc_properties(raw_oc_properties)

    assert catalog.get_oc_properties().get_cos_object() is raw_oc_properties


def test_catalog_find_named_destination_ignores_bad_names_dictionary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _NamedDestination:
        def get_named_destination(self) -> str:
            return "Chapter1"

    class _BadNames:
        def get_dests(self) -> object:
            raise RuntimeError("bad names")

    with PDDocument() as doc:
        catalog = doc.get_document_catalog()
        monkeypatch.setattr(catalog, "get_names", lambda: _BadNames())

        assert catalog.find_named_destination_page(_NamedDestination()) is None


def test_catalog_has_output_intents_false_when_entry_is_absent() -> None:
    with PDDocument() as doc:
        assert doc.get_document_catalog().has_output_intents() is False
