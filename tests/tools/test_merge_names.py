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


def _name_tree_entries(doc: PDDocument, category: COSName) -> list[tuple[str, object]]:
    """Return the flat ``/Names`` array under ``category`` as an ordered
    list of ``(name, value)`` pairs.

    Upstream :class:`PDFMergerUtility` appends source entries to the
    destination's flat array verbatim, so duplicate names ride along
    in array order — this helper preserves that ordering for assertions.
    """
    names = doc.get_document_catalog().get_cos_object().get_dictionary_object(_NAMES)
    assert isinstance(names, COSDictionary)
    tree = names.get_dictionary_object(category)
    assert isinstance(tree, COSDictionary)
    arr = tree.get_dictionary_object(_NAMES)
    assert isinstance(arr, COSArray)
    out: list[tuple[str, object]] = []
    i = 0
    while i + 1 < arr.size():
        key = arr.get_object(i)
        assert isinstance(key, COSString)
        out.append((key.get_string(), arr.get_object(i + 1)))
        i += 2
    return out


def test_merge_keeps_duplicate_names_in_flat_array(tmp_path: Path) -> None:
    """Upstream :class:`PDFMergerUtility` lets duplicate name-tree keys
    ride along in the merged ``/Names`` array; the tool no longer rewrites
    them as ``name#2`` (the prior pypdfbox divergence — see CHANGES.md
    wave 1374)."""
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
        dest_entries = _name_tree_entries(merged, _DESTS)
        dest_names = [name for name, _value in dest_entries]
        # Duplicates ride along — no ``#2`` rename.
        assert dest_names == ["intro", "intro"]
        # The two destination arrays point at the imported A-page and
        # B-page respectively (clone identity is preserved within each
        # source by ``PDFCloneUtility``'s identity table).
        first_dest = dest_entries[0][1]
        second_dest = dest_entries[1][1]
        assert isinstance(first_dest, COSArray)
        assert isinstance(second_dest, COSArray)
        assert first_dest.get_object(0) is pages[0].get_cos_object()
        assert second_dest.get_object(0) is pages[1].get_cos_object()

        scripts = [name for name, _value in _name_tree_entries(merged, _JAVA_SCRIPT)]
        assert scripts == ["boot", "boot"]

        embedded = [
            name for name, _value in _name_tree_entries(merged, _EMBEDDED_FILES)
        ]
        assert embedded == ["attachment.txt", "attachment.txt"]


def test_merge_named_destination_link_stays_unsuffixed(tmp_path: Path) -> None:
    """When source B carries a ``PDNamedDestination`` link, upstream
    behaviour leaves the destination name intact (``go``) and stores both
    ``go`` entries side by side in the merged ``/Names /Dests`` flat
    array. The previous pypdfbox port rewrote it to ``go#2`` — this test
    locks in the upstream-faithful behaviour after wave 1374."""
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
        # No #2 rename — the named destination still resolves through the
        # /Dests name tree, which now contains two ``go`` entries.
        assert dest.get_string() == "go"

        dest_entries = _name_tree_entries(merged, _DESTS)
        assert [name for name, _value in dest_entries] == ["go", "go"]
        # The B-side ``go`` entry (second one in array order) still points
        # at the imported B-page.
        b_dest = dest_entries[1][1]
        assert isinstance(b_dest, COSArray)
        assert b_dest.get_object(0) is pages[1].get_cos_object()
