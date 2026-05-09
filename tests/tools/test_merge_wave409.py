from __future__ import annotations

import argparse

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSObject, COSString
from pypdfbox.pdmodel import PDDocument
from pypdfbox.tools import merge


def test_build_parser_registers_merge_command() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()

    merge.build_parser(subparsers)
    args = parser.parse_args(["merge", "-i", "a.pdf", "b.pdf", "-o", "out.pdf"])

    assert args.inputs == ["a.pdf", "b.pdf"]
    assert args.output == "out.pdf"
    assert args.func is merge.run


def test_collect_name_tree_entries_walks_kids_and_skips_malformed_pairs() -> None:
    root = COSDictionary()
    root_names = COSArray()
    root_names.add(COSString("root"))
    root_names.add(COSName.get_pdf_name("RootValue"))
    root_names.add(COSDictionary())
    root_names.add(COSName.get_pdf_name("SkippedBecauseKeyIsNotText"))
    root_names.add(COSString("dangling"))
    root.set_item("Names", root_names)

    child = COSDictionary()
    child_names = COSArray()
    child_names.add(COSName.get_pdf_name("child"))
    child_names.add(COSString("ChildValue"))
    child.set_item("Names", child_names)
    kids = COSArray()
    kids.add(child)
    kids.add(COSName.get_pdf_name("NotADictionary"))
    root.set_item("Kids", kids)

    entries = merge._collect_name_tree_entries(root)

    assert entries == [
        ("root", COSName.get_pdf_name("RootValue")),
        ("child", COSString("ChildValue")),
    ]


def test_set_flat_name_tree_entries_sorts_deduplicates_and_removes_kids() -> None:
    tree = COSDictionary()
    tree.set_item("Kids", COSArray())

    merge._set_flat_name_tree_entries(
        tree,
        [
            ("zeta", COSString("old")),
            ("alpha", COSString("first")),
            ("zeta", COSString("new")),
        ],
    )

    names = tree.get_dictionary_object("Names")
    assert isinstance(names, COSArray)
    assert tree.get_dictionary_object("Kids") is None
    assert [names.get_object(0).get_string(), names.get_object(2).get_string()] == [
        "alpha",
        "zeta",
    ]
    assert names.get_object(3).get_string() == "new"


def test_deduplicate_name_skips_existing_suffixes() -> None:
    used = {"intro", "intro#2", "intro#3"}

    assert merge._deduplicate_name("summary", used) == "summary"
    assert merge._deduplicate_name("intro", used) == "intro#4"


def test_remap_dest_array_uses_object_key_before_resolving_reference() -> None:
    original_page = COSDictionary()
    source_ref = COSObject(25, 2, resolved=original_page)
    imported_page = COSDictionary()
    src_dest = COSArray([source_ref])
    new_dest = COSArray([COSDictionary()])

    merge._remap_dest_array(
        src_dest,
        new_dest,
        {merge._object_key(source_ref): imported_page},
    )

    assert new_dest.get(0) is imported_page


def test_remap_dest_array_handles_direct_dict_and_ignores_non_matches() -> None:
    original_page = COSDictionary()
    imported_page = COSDictionary()
    direct_src = COSArray([original_page])
    direct_new = COSArray([COSDictionary()])

    merge._remap_dest_array(
        direct_src,
        direct_new,
        {("id", id(original_page)): imported_page},
    )

    assert direct_new.get(0) is imported_page

    short_src = COSArray()
    short_new = COSArray([COSDictionary()])
    merge._remap_dest_array(short_src, short_new, {("id", id(original_page)): imported_page})
    assert short_new.get(0) is not imported_page

    name_src = COSArray([COSName.get_pdf_name("NamedDest")])
    name_new = COSArray([COSDictionary()])
    merge._remap_dest_array(name_src, name_new, {("id", id(original_page)): imported_page})
    assert name_new.get(0) is not imported_page


def test_remap_destination_value_handles_dictionary_d_entry() -> None:
    original_page = COSDictionary()
    imported_page = COSDictionary()
    src_value = COSDictionary()
    new_value = COSDictionary()
    src_value.set_item("D", COSArray([original_page]))
    new_dest = COSArray([COSDictionary()])
    new_value.set_item("D", new_dest)

    merge._remap_destination_value(
        src_value,
        new_value,
        {("id", id(original_page)): imported_page},
    )

    assert new_dest.get(0) is imported_page


def test_renamed_dest_value_accepts_string_and_name_sources() -> None:
    renamed = {"chapter": "chapter#2"}

    from_string = merge._renamed_dest_value(COSString("chapter"), renamed)
    from_name = merge._renamed_dest_value(COSName.get_pdf_name("chapter"), renamed)

    assert from_string is not None
    assert from_string.get_string() == "chapter#2"
    assert from_name is not None
    assert from_name.get_string() == "chapter#2"
    assert merge._renamed_dest_value(COSString("missing"), renamed) is None
    assert merge._renamed_dest_value(COSArray(), renamed) is None


def test_remap_page_links_uses_min_length_and_skips_non_links() -> None:
    source_target = COSDictionary()
    imported_target = COSDictionary()
    src_page = COSDictionary()
    new_page = COSDictionary()
    src_annots = COSArray()
    new_annots = COSArray()

    non_link = COSDictionary()
    non_link.set_name("Subtype", "Text")
    non_link.set_item("Dest", COSArray([source_target]))
    src_annots.add(non_link)
    new_non_link = COSDictionary()
    new_non_link.set_item("Dest", COSArray([COSDictionary()]))
    new_annots.add(new_non_link)

    link = COSDictionary()
    link.set_name("Subtype", "Link")
    link.set_item("Dest", COSString("oldName"))
    src_annots.add(link)
    new_link = COSDictionary()
    new_annots.add(new_link)

    src_annots.add(COSDictionary())
    src_page.set_item("Annots", src_annots)
    new_page.set_item("Annots", new_annots)

    merge._remap_page_links(
        src_page,
        new_page,
        {("id", id(source_target)): imported_target},
        {"oldName": "newName"},
    )

    assert new_non_link.get_dictionary_object("Dest").get(0) is not imported_target  # type: ignore[union-attr]
    rewritten = new_link.get_dictionary_object("Dest")
    assert isinstance(rewritten, COSString)
    assert rewritten.get_string() == "newName"


def test_merge_supported_names_removes_empty_target_names_dictionary() -> None:
    src = PDDocument()
    target = PDDocument()
    try:
        merge._merge_supported_names(src, target, {})
        catalog = target.get_document_catalog().get_cos_object()
        assert catalog.get_dictionary_object("Names") is None
    finally:
        src.close()
        target.close()


def test_collect_page_object_keys_handles_cycles_and_page_like_nodes() -> None:
    page_dict = COSDictionary()
    page_dict.set_name("Type", "Page")
    page_ref = COSObject(7, 0, resolved=page_dict)
    page_like = COSDictionary()
    page_like.set_name("Type", "SomethingElse")
    root = COSDictionary()
    root.set_name("Type", "Pages")
    kids = COSArray([page_ref, page_like, root])
    root.set_item("Kids", kids)

    keys: list[tuple[str, int, int] | None] = []
    merge._collect_page_object_keys(root, None, keys, set())

    assert keys == [("obj", 7, 0), None]
