"""Catalog /Names reconciliation tests for ``pypdfbox merge``."""
from __future__ import annotations

from pathlib import Path

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSString
from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.pdmodel.common.filespecification.pd_complex_file_specification import (
    PDComplexFileSpecification,
)
from pypdfbox.pdmodel.interactive.annotation import PDAnnotationLink
from pypdfbox.pdmodel.interactive.documentnavigation.destination import (
    PDNamedDestination,
    PDPageFitDestination,
)
from pypdfbox.tools import cli

_A = COSName.get_pdf_name("A")
_ANNOTS = COSName.get_pdf_name("Annots")
_D = COSName.get_pdf_name("D")
_DEST = COSName.get_pdf_name("Dest")
_DESTS = COSName.get_pdf_name("Dests")
_EMBEDDED_FILES = COSName.get_pdf_name("EmbeddedFiles")
_JAVA_SCRIPT = COSName.get_pdf_name("JavaScript")
_JS = COSName.get_pdf_name("JS")
_NAMES = COSName.get_pdf_name("Names")


def _build_pdf_with_names(
    path: Path,
    *,
    dest_name: str,
    js_name: str = "boot",
    file_name: str = "attachment.txt",
    link_to_named_dest: bool = False,
) -> Path:
    doc = PDDocument()
    try:
        page = PDPage()
        doc.add_page(page)

        dest = PDPageFitDestination()
        dest.set_page(page.get_cos_object())

        js_action = COSDictionary()
        js_action.set_name("Type", "Action")
        js_action.set_name("S", "JavaScript")
        js_action.set_string(_JS, f"app.alert('{js_name}')")

        spec = PDComplexFileSpecification()
        spec.set_file(file_name)

        catalog = doc.get_document_catalog().get_cos_object()
        names = COSDictionary()
        catalog.set_item(_NAMES, names)
        _set_flat_name_tree(names, _DESTS, [(dest_name, dest.get_cos_object())])
        _set_flat_name_tree(names, _JAVA_SCRIPT, [(js_name, js_action)])
        _set_flat_name_tree(
            names, _EMBEDDED_FILES, [(file_name, spec.get_cos_object())]
        )

        if link_to_named_dest:
            link = PDAnnotationLink()
            link.set_destination(PDNamedDestination(dest_name))
            page.set_annotations([link])

        doc.save(path)
    finally:
        doc.close()
    return path


def _set_flat_name_tree(
    names: COSDictionary,
    category: COSName,
    entries: list[tuple[str, object]],
) -> None:
    tree = COSDictionary()
    arr = COSArray()
    for name, value in entries:
        arr.add(COSString(name))
        arr.add(value)
    tree.set_item(_NAMES, arr)
    names.set_item(category, tree)


def _name_tree_entries(doc: PDDocument, category: COSName) -> dict[str, object]:
    names = doc.get_document_catalog().get_cos_object().get_dictionary_object(_NAMES)
    assert isinstance(names, COSDictionary)
    tree = names.get_dictionary_object(category)
    assert isinstance(tree, COSDictionary)
    arr = tree.get_dictionary_object(_NAMES)
    assert isinstance(arr, COSArray)
    out: dict[str, object] = {}
    i = 0
    while i + 1 < arr.size():
        key = arr.get_object(i)
        assert isinstance(key, COSString)
        out[key.get_string()] = arr.get_object(i + 1)
        i += 2
    return out


def test_merge_preserves_supported_names_with_deterministic_suffixes(
    tmp_path: Path,
) -> None:
    a = _build_pdf_with_names(
        tmp_path / "a.pdf",
        dest_name="intro",
        js_name="boot",
        file_name="attachment.txt",
    )
    b = _build_pdf_with_names(
        tmp_path / "b.pdf",
        dest_name="intro",
        js_name="boot",
        file_name="attachment.txt",
    )
    out = tmp_path / "out.pdf"

    rc = cli.run_cli(["merge", "-i", str(a), str(b), "-o", str(out)])
    assert rc == 0

    with PDDocument.load(out) as merged:
        pages = list(merged.get_pages())
        dests = _name_tree_entries(merged, _DESTS)
        assert sorted(dests) == ["intro", "intro#2"]
        first_dest = dests["intro"]
        second_dest = dests["intro#2"]
        assert isinstance(first_dest, COSArray)
        assert isinstance(second_dest, COSArray)
        assert first_dest.get_object(0) is pages[0].get_cos_object()
        assert second_dest.get_object(0) is pages[1].get_cos_object()

        scripts = _name_tree_entries(merged, _JAVA_SCRIPT)
        assert sorted(scripts) == ["boot", "boot#2"]
        assert isinstance(scripts["boot"], COSDictionary)
        assert scripts["boot"].get_string(_JS) == "app.alert('boot')"

        embedded = _name_tree_entries(merged, _EMBEDDED_FILES)
        assert sorted(embedded) == ["attachment.txt", "attachment.txt#2"]


def test_merge_rewrites_named_destination_links_when_name_is_suffixed(
    tmp_path: Path,
) -> None:
    a = _build_pdf_with_names(tmp_path / "a.pdf", dest_name="go")
    b = _build_pdf_with_names(
        tmp_path / "b.pdf",
        dest_name="go",
        link_to_named_dest=True,
    )
    out = tmp_path / "out.pdf"

    rc = cli.run_cli(["merge", "-i", str(a), str(b), "-o", str(out)])
    assert rc == 0

    with PDDocument.load(out) as merged:
        pages = list(merged.get_pages())
        annots = pages[1].get_cos_object().get_dictionary_object(_ANNOTS)
        assert isinstance(annots, COSArray)
        link = annots.get_object(0)
        assert isinstance(link, COSDictionary)
        dest = link.get_dictionary_object(_DEST)
        assert isinstance(dest, COSString)
        assert dest.get_string() == "go#2"

        action = link.get_dictionary_object(_A)
        if isinstance(action, COSDictionary):
            action_dest = action.get_dictionary_object(_D)
            assert not isinstance(action_dest, COSString)

        dests = _name_tree_entries(merged, _DESTS)
        renamed_dest = dests["go#2"]
        assert isinstance(renamed_dest, COSArray)
        assert renamed_dest.get_object(0) is pages[1].get_cos_object()
