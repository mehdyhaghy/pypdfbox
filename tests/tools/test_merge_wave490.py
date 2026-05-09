from __future__ import annotations

from argparse import Namespace
from pathlib import Path

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSString
from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.tools import merge

_D = COSName.get_pdf_name("D")
_DESTS = COSName.get_pdf_name("Dests")
_LANG = COSName.get_pdf_name("Lang")
_METADATA = COSName.get_pdf_name("Metadata")
_NAMES = COSName.get_pdf_name("Names")
_PAGE_LAYOUT = COSName.get_pdf_name("PageLayout")


def _save_one_page(path: Path) -> None:
    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        doc.save(path)
    finally:
        doc.close()


def test_wave490_run_reports_save_oserror_and_closes_sources(
    tmp_path: Path,
    capsys,
    monkeypatch,
) -> None:
    first = tmp_path / "first.pdf"
    second = tmp_path / "second.pdf"
    _save_one_page(first)
    _save_one_page(second)

    def broken_save(self: PDDocument, _output: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(PDDocument, "save", broken_save)

    rc = merge.run(
        Namespace(inputs=[str(first), str(second)], output=str(tmp_path / "out.pdf"))
    )

    assert rc == 4
    assert "Error merging documents [OSError]: disk full" in capsys.readouterr().out


def test_wave490_preserve_simple_catalog_entries_uses_first_source_value() -> None:
    src = PDDocument()
    target = PDDocument()
    try:
        src_catalog = src.get_document_catalog().get_cos_object()
        target_catalog = target.get_document_catalog().get_cos_object()
        metadata = COSDictionary()
        metadata.set_string("Producer", "pypdfbox")
        src_catalog.set_item(_LANG, COSString("en-US"))
        src_catalog.set_item(_PAGE_LAYOUT, COSName.get_pdf_name("SinglePage"))
        src_catalog.set_item(_METADATA, metadata)
        target_catalog.set_item(_LANG, COSString("fr-FR"))

        merge._preserve_simple_catalog_entries(src, target)

        assert target_catalog.get_dictionary_object(_LANG).get_string() == "fr-FR"
        assert target_catalog.get_dictionary_object(_PAGE_LAYOUT) == COSName.get_pdf_name(
            "SinglePage"
        )
        copied_metadata = target_catalog.get_dictionary_object(_METADATA)
        assert copied_metadata is not metadata
        assert copied_metadata.get_string("Producer") == "pypdfbox"
    finally:
        src.close()
        target.close()


def test_wave490_merge_name_tree_category_preserves_non_destination_values() -> None:
    target = PDDocument()
    try:
        original_page = COSDictionary()
        imported_page = COSDictionary()
        src_value = COSDictionary()
        src_value.set_item(_D, COSArray([original_page]))
        src_tree = COSDictionary()
        src_tree.set_item(_NAMES, COSArray([COSString("file"), src_value]))
        src_names = COSDictionary()
        src_names.set_item(_METADATA, src_tree)
        target_names = COSDictionary()

        renamed = merge._merge_name_tree_category(
            src_names,
            target_names,
            _METADATA,
            target,
            {("id", id(original_page)): imported_page},
            remap_destinations=False,
        )

        assert renamed == {}
        entries = merge._collect_name_tree_entries(
            target_names.get_dictionary_object(_METADATA)
        )
        assert entries[0][0] == "file"
        assert entries[0][1].get_dictionary_object(_D).get(0) is not imported_page
    finally:
        target.close()


def test_wave490_merge_legacy_dests_skips_empty_values_and_removes_kids() -> None:
    target = PDDocument()
    try:
        target_names = COSDictionary()
        target_tree = COSDictionary()
        child = COSDictionary()
        child.set_item(_NAMES, COSArray([COSString("existing"), COSString("old")]))
        target_tree.set_item("Kids", COSArray([child]))
        target_names.set_item(_DESTS, target_tree)

        legacy_dests = COSDictionary()
        legacy_dests.set_item("missing", None)
        legacy_dests.set_item("new", COSArray([COSName.get_pdf_name("NamedDest")]))

        renamed = merge._merge_legacy_dests(legacy_dests, target_names, target, {})

        assert renamed == {}
        entries = merge._collect_name_tree_entries(target_tree)
        assert [name for name, _value in entries] == ["existing", "new"]
        assert target_tree.get_dictionary_object("Kids") is None
    finally:
        target.close()


def test_wave490_remap_destination_value_ignores_non_array_dictionary_d() -> None:
    src_value = COSDictionary()
    src_value.set_item(_D, COSString("named"))
    new_value = COSDictionary()
    new_value.set_item(_D, COSString("named"))

    merge._remap_destination_value(src_value, new_value, {})

    assert new_value.get_dictionary_object(_D).get_string() == "named"


def test_wave490_remap_one_link_leaves_missing_new_action_untouched() -> None:
    src_action = COSDictionary()
    src_action.set_name("S", "GoTo")
    src_action.set_item("D", COSString("intro"))
    src_annot = COSDictionary()
    src_annot.set_name("Subtype", "Link")
    src_annot.set_item("A", src_action)
    new_annot = COSDictionary()

    merge._remap_one_link(src_annot, new_annot, {}, {"intro": "intro#2"})

    assert new_annot.get_dictionary_object("A") is None


def test_wave490_source_page_object_keys_returns_none_for_direct_pages() -> None:
    doc = PDDocument()
    try:
        doc.add_page(PDPage())

        assert merge._source_page_object_keys(doc) == [None]
    finally:
        doc.close()
