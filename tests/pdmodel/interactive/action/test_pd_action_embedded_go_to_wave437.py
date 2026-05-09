from __future__ import annotations

import io

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.common.filespecification.pd_complex_file_specification import (
    PDComplexFileSpecification,
)
from pypdfbox.pdmodel.common.filespecification.pd_embedded_file import (
    PDEmbeddedFile,
)
from pypdfbox.pdmodel.interactive.action.pd_action_embedded_go_to import (
    PDActionEmbeddedGoTo,
)
from pypdfbox.pdmodel.interactive.action.pd_target_directory import (
    PDTargetDirectory,
)
from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_named_destination import (
    PDNamedDestination,
)
from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_page_destination import (
    PDPageDestination,
)
from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_page_fit_destination import (
    PDPageFitDestination,
)
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_document_name_dictionary import PDDocumentNameDictionary
from pypdfbox.pdmodel.pd_embedded_files_name_tree_node import (
    PDEmbeddedFilesNameTreeNode,
)
from pypdfbox.pdmodel.pd_page import PDPage


def _make_pdf_bytes(page_count: int = 1) -> bytes:
    doc = PDDocument()
    for _ in range(page_count):
        doc.add_page(PDPage())
    out = io.BytesIO()
    doc.save(out)
    doc.close()
    return out.getvalue()


def _attach_file_spec(
    doc: PDDocument,
    name: str,
    spec: PDComplexFileSpecification,
) -> None:
    catalog = doc.get_document_catalog()
    names = catalog.get_names() or PDDocumentNameDictionary(catalog=catalog)
    embedded_files = names.get_embedded_files() or PDEmbeddedFilesNameTreeNode()
    current = embedded_files.get_names() or {}
    current[name] = spec
    embedded_files.set_names(current)
    names.set_embedded_files(embedded_files)


def _targeting_action(filename: str, page_number: int = 0) -> PDActionEmbeddedGoTo:
    action = PDActionEmbeddedGoTo()
    target = PDTargetDirectory()
    target.set_target_filename(filename)
    action.set_target(target)
    dest = PDPageFitDestination()
    dest.set_page_number(page_number)
    action.set_d(dest)
    return action


def test_wave437_resolve_target_returns_none_without_names_dictionary() -> None:
    source = PDDocument()
    action = _targeting_action("missing.pdf")

    assert action.resolve_target(source) is None

    source.close()


def test_wave437_resolve_target_returns_none_without_embedded_files_tree() -> None:
    source = PDDocument()
    source.get_document_catalog().set_names(
        PDDocumentNameDictionary(catalog=source.get_document_catalog())
    )
    action = _targeting_action("missing.pdf")

    assert action.resolve_target(source) is None

    source.close()


def test_wave437_resolve_target_uses_unicode_embedded_file_fallback() -> None:
    source = PDDocument()
    spec = PDComplexFileSpecification()
    spec.set_file("child.pdf")
    embedded = PDEmbeddedFile(source, _make_pdf_bytes(page_count=2))
    spec.set_embedded_file_unicode(embedded)
    _attach_file_spec(source, "child.pdf", spec)
    action = _targeting_action("child.pdf", page_number=1)

    result = action.resolve_target(source)

    assert result is not None
    final_doc, final_dest = result
    assert final_doc is not source
    assert final_doc.get_number_of_pages() == 2
    assert isinstance(final_dest, PDPageDestination)
    assert final_dest.get_page_number() == 1
    final_doc.close()
    source.close()


def test_wave437_resolve_target_soft_fails_for_empty_embedded_file() -> None:
    source = PDDocument()
    spec = PDComplexFileSpecification()
    spec.set_file("empty.pdf")
    spec.set_embedded_file(PDEmbeddedFile(source, b""))
    _attach_file_spec(source, "empty.pdf", spec)
    action = _targeting_action("empty.pdf")

    assert action.resolve_target(source) is None

    source.close()


def test_wave437_resolve_target_soft_fails_for_non_pdf_payload() -> None:
    source = PDDocument()
    spec = PDComplexFileSpecification()
    spec.set_file("notes.txt")
    spec.set_embedded_file(PDEmbeddedFile(source, b"not a pdf"))
    _attach_file_spec(source, "notes.txt", spec)
    action = _targeting_action("notes.txt")

    assert action.resolve_target(source) is None

    source.close()


def test_wave437_named_destination_missing_returns_none() -> None:
    source = PDDocument()
    action = PDActionEmbeddedGoTo()
    action.set_d(PDNamedDestination("NoSuchDestination"))

    assert action.resolve_target(source) is None

    source.close()


def test_wave437_legacy_catalog_dests_resolves_named_destination() -> None:
    source = PDDocument()
    dests = COSDictionary()
    dest = PDPageFitDestination()
    dest.set_page_number(0)
    dests.set_item(COSName.get_pdf_name("LegacyName"), dest.get_cos_object())
    source.get_document_catalog().get_cos_object().set_item(
        COSName.get_pdf_name("Dests"), dests
    )
    action = PDActionEmbeddedGoTo()
    action.set_d(PDNamedDestination("LegacyName"))

    result = action.resolve_target(source)

    assert result is not None
    final_doc, final_dest = result
    assert final_doc is source
    assert isinstance(final_dest, PDPageDestination)
    assert final_dest.get_page_number() == 0
    source.close()


def test_wave437_walk_to_target_stops_on_cycle_after_recording_steps() -> None:
    first = PDTargetDirectory()
    first.set_relationship("C")
    first.set_target_filename("child.pdf")
    first.set_page_number(3)
    first.set_annotation_number(5)
    first.set_target(first)
    action = PDActionEmbeddedGoTo()
    action.set_target(first)

    steps = action.walk_to_target()

    assert len(steps) == 1
    assert steps[0].relationship == "C"
    assert steps[0].target_filename == "child.pdf"
    assert steps[0].page_number == 3
    assert steps[0].annotation_number == 5
