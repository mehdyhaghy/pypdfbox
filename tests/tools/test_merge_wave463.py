from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSObject, COSString
from pypdfbox.pdmodel import PDDocument
from pypdfbox.tools import merge


def test_ensure_names_dictionary_reuses_existing_and_replaces_malformed() -> None:
    catalog = COSDictionary()
    existing = COSDictionary()
    catalog.set_item("Names", existing)

    assert merge._ensure_names_dictionary(catalog) is existing

    catalog.set_name("Names", "Malformed")
    created = merge._ensure_names_dictionary(catalog)

    assert isinstance(created, COSDictionary)
    assert created is catalog.get_dictionary_object("Names")


def test_merge_legacy_dests_deduplicates_and_remaps_page_arrays() -> None:
    target = PDDocument()
    try:
        old_page = COSDictionary()
        imported_page = COSDictionary()
        existing_dest = COSArray([COSDictionary()])
        existing_tree = COSDictionary()
        existing_tree.set_item(
            "Names",
            COSArray([COSString("chapter"), existing_dest]),
        )
        target_names = COSDictionary()
        target_names.set_item("Dests", existing_tree)

        legacy_dests = COSDictionary()
        legacy_dest = COSArray([old_page, COSName.get_pdf_name("Fit")])
        legacy_dests.set_item("chapter", legacy_dest)

        renamed = merge._merge_legacy_dests(
            legacy_dests,
            target_names,
            target,
            {("id", id(old_page)): imported_page},
        )

        assert renamed == {"chapter": "chapter#2"}
        entries = merge._collect_name_tree_entries(existing_tree)
        assert [name for name, _value in entries] == ["chapter", "chapter#2"]
        assert entries[1][1].get(0) is imported_page  # type: ignore[attr-defined]
    finally:
        target.close()


def test_merge_name_tree_category_skips_absent_and_empty_categories() -> None:
    target = PDDocument()
    try:
        src_names = COSDictionary()
        target_names = COSDictionary()

        assert (
            merge._merge_name_tree_category(
                src_names,
                target_names,
                COSName.get_pdf_name("Dests"),
                target,
                {},
                remap_destinations=True,
            )
            == {}
        )

        src_names.set_item("Dests", COSDictionary())
        assert (
            merge._merge_name_tree_category(
                src_names,
                target_names,
                COSName.get_pdf_name("Dests"),
                target,
                {},
                remap_destinations=True,
            )
            == {}
        )
        assert target_names.get_dictionary_object("Dests") is None
    finally:
        target.close()


def test_remap_one_link_rewrites_goto_named_dest_only_for_goto_actions() -> None:
    src_annot = COSDictionary()
    src_annot.set_name("Subtype", "Link")
    src_action = COSDictionary()
    src_action.set_name("S", "GoTo")
    src_action.set_item("D", COSName.get_pdf_name("intro"))
    src_annot.set_item("A", src_action)

    new_annot = COSDictionary()
    new_action = COSDictionary()
    new_action.set_name("S", "GoTo")
    new_annot.set_item("A", new_action)

    merge._remap_one_link(src_annot, new_annot, {}, {"intro": "intro#2"})

    rewritten = new_action.get_dictionary_object("D")
    assert isinstance(rewritten, COSString)
    assert rewritten.get_string() == "intro#2"

    remote_src = COSDictionary()
    remote_src.set_name("Subtype", "Link")
    remote_action = COSDictionary()
    remote_action.set_name("S", "GoToR")
    remote_action.set_item("D", COSString("remote"))
    remote_src.set_item("A", remote_action)
    remote_new = COSDictionary()
    remote_new_action = COSDictionary()
    remote_new.set_item("A", remote_new_action)

    merge._remap_one_link(remote_src, remote_new, {}, {"remote": "remote#2"})

    assert remote_new_action.get_dictionary_object("D") is None


def test_collect_page_object_keys_skips_unresolved_indirect_nodes() -> None:
    keys: list[tuple[str, int, int] | None] = []

    merge._collect_page_object_keys(COSObject(99, 0, resolved=None), None, keys, set())

    assert keys == []
