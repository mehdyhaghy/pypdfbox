"""Tests for ``PDActionEmbeddedGoTo.resolve_target`` — chained ``/T``
walk through ``/Names /EmbeddedFiles`` per PDF 32000-1 §12.6.4.4."""

from __future__ import annotations

import io

from pypdfbox.cos import COSArray, COSDictionary, COSName
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
from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_destination_name_tree_node import (
    PDDestinationNameTreeNode,
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


# ---------- helpers ----------


def _make_pdf_bytes(num_pages: int) -> bytes:
    """Synthesise a minimal saveable PDF with ``num_pages`` blank pages."""
    doc = PDDocument()
    for _ in range(num_pages):
        doc.add_page(PDPage())
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


def _attach_embedded_pdf(
    parent: PDDocument, name: str, pdf_bytes: bytes
) -> None:
    """Attach ``pdf_bytes`` to ``parent``'s ``/Names /EmbeddedFiles`` tree
    under the given ``name``."""
    catalog = parent.get_document_catalog()
    names = catalog.get_names()
    if names is None:
        names = PDDocumentNameDictionary(catalog=catalog)
    efs = names.get_embedded_files()
    if efs is None:
        efs = PDEmbeddedFilesNameTreeNode()
    spec = PDComplexFileSpecification()
    spec.set_file(name)
    embedded = PDEmbeddedFile(parent, pdf_bytes)
    embedded.set_subtype("application/pdf")
    spec.set_embedded_file(embedded)
    existing = efs.get_names() or {}
    existing[name] = spec
    efs.set_names(existing)
    names.set_embedded_files(efs)


def _add_named_destination_to_doc(
    doc: PDDocument, name: str, page_index: int
) -> None:
    """Wire a named destination ``name`` -> /D[page_index, /Fit] under
    ``doc``'s ``/Names /Dests`` name tree."""
    catalog = doc.get_document_catalog()
    cat_cos = catalog.get_cos_object()
    names_dict = cat_cos.get_dictionary_object(COSName.get_pdf_name("Names"))
    if not isinstance(names_dict, COSDictionary):
        names_dict = COSDictionary()
        cat_cos.set_item(COSName.get_pdf_name("Names"), names_dict)
    dests_node = names_dict.get_dictionary_object(COSName.get_pdf_name("Dests"))
    if not isinstance(dests_node, COSDictionary):
        dests_node = COSDictionary()
        names_dict.set_item(COSName.get_pdf_name("Dests"), dests_node)
    tree = PDDestinationNameTreeNode(dests_node)
    dest = PDPageFitDestination()
    dest.set_page_number(page_index)
    tree.set_value(name, dest)


# ---------- tests ----------


def test_resolve_target_single_step_explicit_destination() -> None:
    """One-hop /T: action /T = { /N: "child.pdf", /R: "C" } and /D = [3 /Fit]
    against a source doc whose /Names /EmbeddedFiles holds a tiny child PDF.
    Resolves to the explicit page destination unchanged (page index 3)."""
    child_pdf = _make_pdf_bytes(num_pages=5)
    source = PDDocument()
    _attach_embedded_pdf(source, "child.pdf", child_pdf)

    action = PDActionEmbeddedGoTo()
    target = PDTargetDirectory()
    target.set_relationship("C")
    target.set_target_filename("child.pdf")
    action.set_target(target)

    dest = PDPageFitDestination()
    dest.set_page_number(3)
    action.set_d(dest)

    result = action.resolve_target(source)
    assert result is not None
    final_doc, final_dest = result
    assert isinstance(final_doc, PDDocument)
    assert final_doc is not source  # navigated into the embedded child
    assert final_doc.get_number_of_pages() == 5
    assert isinstance(final_dest, PDPageDestination)
    assert final_dest.get_page_number() == 3
    final_doc.close()
    source.close()


def test_resolve_target_two_step_chain_walks_both_hops() -> None:
    """Two-hop chain: source → child.pdf → grandchild.pdf, ending in a
    [/Fit, page=2] destination. The walker must descend twice."""
    grandchild_pdf = _make_pdf_bytes(num_pages=4)

    # Build a child PDF that itself has /Names /EmbeddedFiles holding the
    # grandchild. We do this by constructing the child as a PDDocument,
    # attaching the grandchild, and then saving to bytes.
    child_doc = PDDocument()
    child_doc.add_page(PDPage())
    _attach_embedded_pdf(child_doc, "grandchild.pdf", grandchild_pdf)
    child_buf = io.BytesIO()
    child_doc.save(child_buf)
    child_doc.close()
    child_pdf = child_buf.getvalue()

    source = PDDocument()
    _attach_embedded_pdf(source, "child.pdf", child_pdf)

    action = PDActionEmbeddedGoTo()
    inner = PDTargetDirectory()
    inner.set_relationship("C")
    inner.set_target_filename("grandchild.pdf")

    outer = PDTargetDirectory()
    outer.set_relationship("C")
    outer.set_target_filename("child.pdf")
    outer.set_target(inner)

    action.set_target(outer)

    dest = PDPageFitDestination()
    dest.set_page_number(2)
    action.set_d(dest)

    result = action.resolve_target(source)
    assert result is not None
    final_doc, final_dest = result
    # We landed in the grandchild — its 4-page count gives it away.
    assert final_doc.get_number_of_pages() == 4
    assert isinstance(final_dest, PDPageDestination)
    assert final_dest.get_page_number() == 2
    final_doc.close()
    source.close()


def test_resolve_target_missing_name_returns_none() -> None:
    """When the /N key is absent from the source's /Names /EmbeddedFiles
    tree the walker returns ``None`` rather than raising."""
    source = PDDocument()
    # Note: deliberately attach *some other* file so the tree is present
    # but doesn't carry "missing.pdf".
    _attach_embedded_pdf(source, "present.pdf", _make_pdf_bytes(1))

    action = PDActionEmbeddedGoTo()
    target = PDTargetDirectory()
    target.set_target_filename("missing.pdf")
    action.set_target(target)

    dest = PDPageFitDestination()
    dest.set_page_number(0)
    action.set_d(dest)

    assert action.resolve_target(source) is None
    source.close()


def test_resolve_target_named_destination_via_dests_tree() -> None:
    """Action with /D as a name string ("Chapter1") is resolved against
    the embedded child's /Names /Dests name tree."""
    # Build the child with a named destination "Chapter1" → page 4.
    child_doc = PDDocument()
    for _ in range(6):
        child_doc.add_page(PDPage())
    _add_named_destination_to_doc(child_doc, "Chapter1", page_index=4)
    child_buf = io.BytesIO()
    child_doc.save(child_buf)
    child_doc.close()
    child_pdf = child_buf.getvalue()

    source = PDDocument()
    _attach_embedded_pdf(source, "child.pdf", child_pdf)

    action = PDActionEmbeddedGoTo()
    target = PDTargetDirectory()
    target.set_target_filename("child.pdf")
    action.set_target(target)
    action.set_d(PDNamedDestination("Chapter1"))

    result = action.resolve_target(source)
    assert result is not None
    final_doc, final_dest = result
    assert final_doc.get_number_of_pages() == 6
    assert isinstance(final_dest, PDPageDestination)
    assert final_dest.get_page_number() == 4
    final_doc.close()
    source.close()


def test_resolve_target_no_chain_resolves_destination_in_source() -> None:
    """Action with /D set but no /T at all: there is no embedded file to
    descend into, so the final destination is resolved against the source
    document itself."""
    source = PDDocument()
    for _ in range(2):
        source.add_page(PDPage())

    action = PDActionEmbeddedGoTo()
    dest = PDPageFitDestination()
    dest.set_page_number(1)
    action.set_d(dest)

    result = action.resolve_target(source)
    assert result is not None
    final_doc, final_dest = result
    assert final_doc is source
    assert isinstance(final_dest, PDPageDestination)
    assert final_dest.get_page_number() == 1
    source.close()


def test_resolve_target_parent_relationship_pops_to_target_document() -> None:
    """A /T with /R = "P" pops back to the supplied ``target_document``
    (the document that owns the attachment hosting this action)."""
    parent = PDDocument()
    for _ in range(3):
        parent.add_page(PDPage())

    # Source is a child PDF — the action lives inside it but wants to go
    # back to its parent.
    source = PDDocument()
    source.add_page(PDPage())

    action = PDActionEmbeddedGoTo()
    target = PDTargetDirectory()
    target.set_relationship("P")
    # /N is required by the spec to identify the parent's filename, but
    # for our walker the lookup is skipped on the parent branch — we only
    # need a non-null filename so the chain isn't reported as broken.
    target.set_target_filename("source.pdf")
    action.set_target(target)

    dest = PDPageFitDestination()
    dest.set_page_number(2)
    action.set_d(dest)

    result = action.resolve_target(source, target_document=parent)
    assert result is not None
    final_doc, final_dest = result
    assert final_doc is parent
    assert isinstance(final_dest, PDPageDestination)
    assert final_dest.get_page_number() == 2
    parent.close()
    source.close()


def test_resolve_target_parent_relationship_without_target_doc_returns_none() -> None:
    """/R = "P" with no ``target_document`` supplied returns ``None``."""
    source = PDDocument()
    source.add_page(PDPage())

    action = PDActionEmbeddedGoTo()
    target = PDTargetDirectory()
    target.set_relationship("P")
    target.set_target_filename("anything.pdf")
    action.set_target(target)
    action.set_d(PDPageFitDestination())

    assert action.resolve_target(source, target_document=None) is None
    source.close()
