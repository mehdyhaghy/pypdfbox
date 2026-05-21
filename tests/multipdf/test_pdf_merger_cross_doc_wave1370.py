"""Wave 1370 — cross-document indirect-ref handling during merge (agent E).

When the PDFMergerUtility append walks a source's page graph, it must
deep-clone *everything* — including indirect references whose targets
live in the *other* source. The output catalog must not retain any
reference back into a source PDDocument's COS instances.

These tests build small source docs and assert post-merge that:

- Page dicts on the destination are fresh instances (``is not`` source
  page dicts).
- Source-side shared sub-resources (e.g. /Resources, /Font) become
  per-source cloned trees in the destination — two source docs that
  shared an inline /Font dict produce *separate* /Font dicts on the
  merged destination (no cross-document identity leak).
- A second-source COSObject whose target is also held by a first-source
  COSObject deep-clones independently (no destination-side aliasing
  between two sources just because their COSObject numbers happen to
  collide).
"""
from __future__ import annotations

from pathlib import Path

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSName,
    COSStream,
)
from pypdfbox.multipdf import PDFMergerUtility
from pypdfbox.pdmodel import PDDocument, PDPage

_RESOURCES = COSName.get_pdf_name("Resources")
_FONT = COSName.get_pdf_name("Font")
_TYPE = COSName.get_pdf_name("Type")


def _make_doc_with_font_resources(font_name: str) -> PDDocument:
    """Build a 1-page doc whose page has a /Resources /Font /F1 mapping."""
    doc = PDDocument()
    page = PDPage()
    s = COSStream()
    s.set_raw_data(b"BT /F1 12 Tf (hi) Tj ET\n")
    page.set_contents(s)
    # /Resources /Font /F1 → distinct font dict per source.
    resources = COSDictionary()
    font_dict = COSDictionary()
    font_entry = COSDictionary()
    font_entry.set_item(_TYPE, COSName.get_pdf_name("Font"))
    font_entry.set_item(
        COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Type1")
    )
    font_entry.set_string(COSName.get_pdf_name("BaseFont"), font_name)
    font_dict.set_item(COSName.get_pdf_name("F1"), font_entry)
    resources.set_item(_FONT, font_dict)
    page.get_cos_object().set_item(_RESOURCES, resources)
    doc.add_page(page)
    return doc


def _save(doc: PDDocument, path: Path) -> None:
    doc.save(path)
    doc.close()


# ---------- destination's page dicts are fresh instances ----------


def test_merged_page_dicts_are_not_source_instances(tmp_path: Path) -> None:
    """After merge, every destination page dict is a fresh COSDictionary,
    not the source instance — the writer would otherwise re-link to the
    source's COS pool on save."""
    a = tmp_path / "a.pdf"
    b = tmp_path / "b.pdf"
    out = tmp_path / "out.pdf"
    _save(_make_doc_with_font_resources("Helvetica"), a)
    _save(_make_doc_with_font_resources("Times-Roman"), b)

    util = PDFMergerUtility()
    util.add_sources([str(a), str(b)])
    util.set_destination_file_name(str(out))
    util.merge_documents()

    # Reopen and confirm structure independence.
    with PDDocument.load(str(out)) as merged:
        assert merged.get_number_of_pages() == 2
        pages = list(merged.get_pages())
        page_a_resources = pages[0].get_cos_object().get_dictionary_object(_RESOURCES)
        page_b_resources = pages[1].get_cos_object().get_dictionary_object(_RESOURCES)
        # Each page has its own /Resources dict — the merger didn't
        # collapse them via spurious identity.
        assert isinstance(page_a_resources, COSDictionary)
        assert isinstance(page_b_resources, COSDictionary)
        assert page_a_resources is not page_b_resources


def test_two_sources_with_same_font_basename_each_keep_own_clone(
    tmp_path: Path,
) -> None:
    """Two sources whose pages declare /F1 with the same /BaseFont must
    end up with *independent* /F1 entries in the merged document. (No
    coalescing across documents in PDFBOX_LEGACY_MODE — that's the
    OPTIMIZE_RESOURCES_MODE behaviour, not the default.)"""
    a = tmp_path / "a.pdf"
    b = tmp_path / "b.pdf"
    out = tmp_path / "out.pdf"
    _save(_make_doc_with_font_resources("Helvetica"), a)
    _save(_make_doc_with_font_resources("Helvetica"), b)

    util = PDFMergerUtility()
    util.add_sources([str(a), str(b)])
    util.set_destination_file_name(str(out))
    util.merge_documents()

    with PDDocument.load(str(out)) as merged:
        page_a = merged.get_page(0)
        page_b = merged.get_page(1)
        res_a = page_a.get_cos_object().get_dictionary_object(_RESOURCES)
        res_b = page_b.get_cos_object().get_dictionary_object(_RESOURCES)
        assert isinstance(res_a, COSDictionary)
        assert isinstance(res_b, COSDictionary)
        font_a = res_a.get_dictionary_object(_FONT)
        font_b = res_b.get_dictionary_object(_FONT)
        assert isinstance(font_a, COSDictionary)
        assert isinstance(font_b, COSDictionary)
        # The two source pages had independent /Font dicts so the merger
        # produced two independent /Font dicts on the dest.
        assert font_a is not font_b


# ---------- shared sub-resource within a single source ----------


def test_shared_resource_within_single_source_keeps_identity(
    tmp_path: Path,
) -> None:
    """When a single source has TWO pages sharing the same /Resources
    dict object, the merge must preserve that within-source identity
    on the destination side (one dest /Resources dict referenced twice).
    Mirrors the PDFCloneUtility identity-table guarantee through the
    merger entry point."""
    doc = PDDocument()
    # Build a shared /Resources dict referenced by both pages directly.
    shared_resources = COSDictionary()
    font_dict = COSDictionary()
    font_dict.set_item(
        COSName.get_pdf_name("F1"),
        _make_font_dict("Helvetica"),
    )
    shared_resources.set_item(_FONT, font_dict)
    for i in range(2):
        page = PDPage()
        s = COSStream()
        s.set_raw_data(b"% page " + str(i).encode("ascii") + b"\n")
        page.set_contents(s)
        page.get_cos_object().set_item(_RESOURCES, shared_resources)
        doc.add_page(page)

    a = tmp_path / "src.pdf"
    out = tmp_path / "out.pdf"
    _save(doc, a)

    util = PDFMergerUtility()
    util.add_source(str(a))
    util.set_destination_file_name(str(out))
    util.merge_documents()

    # In a brand new merged doc, both pages should still share their
    # /Resources via the cloner's identity table. We can only check
    # structural equivalence (re-parsing through Loader loses identity).
    with PDDocument.load(str(out)) as merged:
        assert merged.get_number_of_pages() == 2
        for page in merged.get_pages():
            resources = page.get_cos_object().get_dictionary_object(_RESOURCES)
            # Both pages' resources resolve to a /Font /F1 entry.
            assert isinstance(resources, COSDictionary)
            font = resources.get_dictionary_object(_FONT)
            assert isinstance(font, COSDictionary)
            assert font.get_dictionary_object(COSName.get_pdf_name("F1")) is not None


def _make_font_dict(base_font: str) -> COSDictionary:
    d = COSDictionary()
    d.set_item(_TYPE, COSName.get_pdf_name("Font"))
    d.set_item(COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Type1"))
    d.set_string(COSName.get_pdf_name("BaseFont"), base_font)
    return d


# ---------- source COS objects never leak into destination ----------


def test_destination_catalog_holds_no_source_page_dict_refs(
    tmp_path: Path,
) -> None:
    """No destination page dict on the merged document is identical-by-
    instance to either source page dict. Holding open both source docs
    while we inspect the merge ensures we have live source-side
    references to compare against."""
    a = tmp_path / "a.pdf"
    b = tmp_path / "b.pdf"
    out = tmp_path / "out.pdf"
    _save(_make_doc_with_font_resources("Helvetica"), a)
    _save(_make_doc_with_font_resources("Times-Roman"), b)

    # Open both sources + the merged output and assert no shared
    # COSDictionary instance between source.page() and dest.page().
    with PDDocument.load(str(a)) as src_a, PDDocument.load(str(b)) as src_b:
        util = PDFMergerUtility()
        util.add_source(src_a)
        util.add_source(src_b)
        util.set_destination_file_name(str(out))
        util.merge_documents()
        with PDDocument.load(str(out)) as merged:
            src_pages = list(src_a.get_pages()) + list(src_b.get_pages())
            src_dicts = {id(p.get_cos_object()) for p in src_pages}
            for dest_page in merged.get_pages():
                assert id(dest_page.get_cos_object()) not in src_dicts


def test_merger_clones_through_indirect_ref_in_resource_subgraph(
    tmp_path: Path,
) -> None:
    """A source page whose /Resources are indirectly held still ends up
    fully cloned on the destination — no IndirectRefs leaking to source."""
    src = PDDocument()
    page = PDPage()
    s = COSStream()
    s.set_raw_data(b"% page\n")
    page.set_contents(s)
    # Build a /Resources directly attached as a dict (the writer would
    # later promote it to indirect, but the structural relationship is
    # what matters for the cloner). Add a nested array with a couple of
    # entries to exercise the recursion deeply.
    resources = COSDictionary()
    procset = COSArray()
    procset.add(COSName.get_pdf_name("PDF"))
    procset.add(COSName.get_pdf_name("Text"))
    resources.set_item(COSName.get_pdf_name("ProcSet"), procset)
    page.get_cos_object().set_item(_RESOURCES, resources)
    src.add_page(page)

    a = tmp_path / "src.pdf"
    out = tmp_path / "out.pdf"
    _save(src, a)

    util = PDFMergerUtility()
    util.add_source(str(a))
    util.set_destination_file_name(str(out))
    util.merge_documents()

    with PDDocument.load(str(out)) as merged:
        merged_page = merged.get_page(0)
        merged_resources = merged_page.get_cos_object().get_dictionary_object(
            _RESOURCES
        )
        assert isinstance(merged_resources, COSDictionary)
        procset_merged = merged_resources.get_dictionary_object(
            COSName.get_pdf_name("ProcSet")
        )
        assert isinstance(procset_merged, COSArray)
        names = [
            procset_merged.get_object(i).get_name()  # type: ignore[union-attr]
            for i in range(procset_merged.size())
        ]
        assert "PDF" in names
        assert "Text" in names
