"""Wave 1289 — PDFMergerUtility OPTIMIZE_RESOURCES_MODE cross-document
resource deduplication, annotation /Parent fix-up on page import, and
AcroForm field carryover under the optimize path.

Tests live alongside the rest of the merger suite. Each scenario verifies
a single, narrowly-scoped behaviour described in the wave brief:

- equivalent fonts referenced from two source documents collapse to a
  single shared font subgraph in the destination;
- widget annotations whose /Parent chain reaches an AcroForm field are
  promoted into the destination's /AcroForm /Fields with name-collision
  handling;
- the legacy-fallback "OPTIMIZE_RESOURCES_MODE not yet implemented"
  info log must NOT fire for valid input.
"""
from __future__ import annotations

import io
import logging
from pathlib import Path

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSStream
from pypdfbox.multipdf import DocumentMergeMode, PDFMergerUtility
from pypdfbox.pdmodel import PDDocument, PDPage

# ---------- helpers ----------


_FONT = COSName.get_pdf_name("Font")
_F1 = COSName.get_pdf_name("F1")
_RESOURCES = COSName.get_pdf_name("Resources")
_ANNOTS = COSName.get_pdf_name("Annots")
_PARENT = COSName.get_pdf_name("Parent")
_T = COSName.get_pdf_name("T")
_FIELDS = COSName.get_pdf_name("Fields")
_ACRO_FORM = COSName.get_pdf_name("AcroForm")


def _seed_page_contents(page: PDPage, body: bytes = b"q\n1 0 0 1 0 0 cm Q\n") -> None:
    stream = COSStream()
    stream.set_raw_data(body)
    page.set_contents(stream)


def _make_helvetica_font() -> COSDictionary:
    font = COSDictionary()
    font.set_name("Type", "Font")
    font.set_name("Subtype", "Type1")
    font.set_name("BaseFont", "Helvetica")
    return font


def _build_doc_with_font_resource(num_pages: int = 1) -> PDDocument:
    doc = PDDocument()
    for _ in range(num_pages):
        page = PDPage()
        _seed_page_contents(page)
        font = _make_helvetica_font()
        font_map = COSDictionary()
        font_map.set_item(_F1, font)
        resources = COSDictionary()
        resources.set_item(_FONT, font_map)
        page.get_cos_object().set_item(_RESOURCES, resources)
        doc.add_page(page)
    return doc


def _save(doc: PDDocument, path: Path) -> None:
    doc.save(path)
    doc.close()


# ---------- optimize-mode cross-document resource dedup ----------


def test_wave1289_optimize_mode_runs_without_legacy_fallback_log(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """The legacy-fallback "OPTIMIZE_RESOURCES_MODE not yet implemented"
    info log must not fire when valid sources are supplied — the real
    optimised path now runs end-to-end."""
    a = tmp_path / "a.pdf"
    b = tmp_path / "b.pdf"
    out = tmp_path / "out.pdf"
    _save(_build_doc_with_font_resource(2), a)
    _save(_build_doc_with_font_resource(1), b)

    util = PDFMergerUtility()
    util.set_document_merge_mode(DocumentMergeMode.OPTIMIZE_RESOURCES_MODE)
    util.add_sources([str(a), str(b)])
    util.set_destination_file_name(str(out))

    with caplog.at_level(
        logging.INFO, logger="pypdfbox.multipdf.pdf_merger_utility"
    ):
        util.merge_documents()

    assert (
        "OPTIMIZE_RESOURCES_MODE not yet implemented" not in caplog.text
    )
    assert "falling back to PDFBOX_LEGACY_MODE" not in caplog.text
    with PDDocument.load(str(out)) as merged:
        assert merged.get_number_of_pages() == 3


def test_wave1289_optimize_mode_dedups_equivalent_fonts_across_sources(
    tmp_path: Path,
) -> None:
    """Three source PDFs each carry an identical Helvetica /F1 font.
    In OPTIMIZE_RESOURCES_MODE the destination must share one font
    instance across every page rather than emit three independent
    clones."""
    a = tmp_path / "a.pdf"
    b = tmp_path / "b.pdf"
    c = tmp_path / "c.pdf"
    out = tmp_path / "out.pdf"
    _save(_build_doc_with_font_resource(1), a)
    _save(_build_doc_with_font_resource(1), b)
    _save(_build_doc_with_font_resource(1), c)

    util = PDFMergerUtility()
    util.set_document_merge_mode(DocumentMergeMode.OPTIMIZE_RESOURCES_MODE)
    util.add_sources([str(a), str(b), str(c)])
    util.set_destination_file_name(str(out))
    util.merge_documents()

    with PDDocument.load(str(out)) as merged:
        assert merged.get_number_of_pages() == 3
        fonts = []
        for i in range(3):
            page = merged.get_page(i)
            r = page.get_cos_object().get_dictionary_object(_RESOURCES)
            assert isinstance(r, COSDictionary)
            fmap = r.get_dictionary_object(_FONT)
            assert isinstance(fmap, COSDictionary)
            f = fmap.get_dictionary_object(_F1)
            assert isinstance(f, COSDictionary)
            fonts.append(f)
        # The hash-keyed cross-document dedup collapses identical font
        # dicts to one shared instance.
        assert fonts[0] is fonts[1] is fonts[2]
        assert fonts[0].get_name("BaseFont") == "Helvetica"


def test_wave1289_optimize_mode_keeps_distinct_fonts_distinct(
    tmp_path: Path,
) -> None:
    """Two sources, two genuinely different fonts (Helvetica vs
    Times-Roman). The dedup must keep them as two separate objects."""
    a = tmp_path / "a.pdf"
    b = tmp_path / "b.pdf"
    out = tmp_path / "out.pdf"

    def _build(font_name: str) -> PDDocument:
        doc = PDDocument()
        page = PDPage()
        _seed_page_contents(page)
        font = COSDictionary()
        font.set_name("Type", "Font")
        font.set_name("Subtype", "Type1")
        font.set_name("BaseFont", font_name)
        font_map = COSDictionary()
        font_map.set_item(_F1, font)
        resources = COSDictionary()
        resources.set_item(_FONT, font_map)
        page.get_cos_object().set_item(_RESOURCES, resources)
        doc.add_page(page)
        return doc

    _save(_build("Helvetica"), a)
    _save(_build("Times-Roman"), b)

    util = PDFMergerUtility()
    util.set_document_merge_mode(DocumentMergeMode.OPTIMIZE_RESOURCES_MODE)
    util.add_sources([str(a), str(b)])
    util.set_destination_file_name(str(out))
    util.merge_documents()

    with PDDocument.load(str(out)) as merged:
        f0 = (
            merged.get_page(0)
            .get_cos_object()
            .get_dictionary_object(_RESOURCES)
            .get_dictionary_object(_FONT)
            .get_dictionary_object(_F1)
        )
        f1 = (
            merged.get_page(1)
            .get_cos_object()
            .get_dictionary_object(_RESOURCES)
            .get_dictionary_object(_FONT)
            .get_dictionary_object(_F1)
        )
        assert f0.get_name("BaseFont") == "Helvetica"
        assert f1.get_name("BaseFont") == "Times-Roman"
        assert f0 is not f1


def test_wave1289_optimize_mode_to_stream_works(tmp_path: Path) -> None:
    """Destination-stream variant of the optimize path."""
    a = tmp_path / "a.pdf"
    _save(_build_doc_with_font_resource(2), a)
    sink = io.BytesIO()
    util = PDFMergerUtility()
    util.set_document_merge_mode(DocumentMergeMode.OPTIMIZE_RESOURCES_MODE)
    util.add_source(str(a))
    util.set_destination_stream(sink)
    util.merge_documents()
    payload = sink.getvalue()
    assert payload.startswith(b"%PDF-")
    with PDDocument.load(payload) as merged:
        assert merged.get_number_of_pages() == 2


# ---------- AcroForm carryover under optimize ----------


def _build_doc_with_acroform_field(field_name: str) -> PDDocument:
    doc = PDDocument()
    page = PDPage()
    _seed_page_contents(page)
    doc.add_page(page)

    field_dict = COSDictionary()
    field_dict.set_name("FT", "Tx")
    field_dict.set_string(_T, field_name)
    fields_array = COSArray()
    fields_array.add(field_dict)

    acro_form = COSDictionary()
    acro_form.set_item(_FIELDS, fields_array)
    doc.get_document_catalog().get_cos_object().set_item(_ACRO_FORM, acro_form)
    return doc


def test_wave1289_optimize_mode_carries_over_acroform_fields_from_source(
    tmp_path: Path,
) -> None:
    """AcroForm fields from the (only) source must end up in the
    destination's /AcroForm /Fields under the optimize path."""
    a = tmp_path / "a.pdf"
    out = tmp_path / "out.pdf"
    _save(_build_doc_with_acroform_field("Field1"), a)

    util = PDFMergerUtility()
    util.set_document_merge_mode(DocumentMergeMode.OPTIMIZE_RESOURCES_MODE)
    util.add_source(str(a))
    util.set_destination_file_name(str(out))
    util.merge_documents()

    with PDDocument.load(str(out)) as merged:
        form = merged.get_document_catalog().get_acro_form()
        assert form is not None
        names = [f.get_partial_name() for f in form.get_fields()]
        assert names == ["Field1"]


def test_wave1289_optimize_mode_acroform_name_collision_is_uniquified(
    tmp_path: Path,
) -> None:
    """Two sources, both with a /T = 'common' field. Optimize-mode
    AcroForm merge must keep the first one verbatim and rename the
    second with the dummyFieldName-prefix collision-handling rule."""
    a = tmp_path / "a.pdf"
    b = tmp_path / "b.pdf"
    out = tmp_path / "out.pdf"
    _save(_build_doc_with_acroform_field("common"), a)
    _save(_build_doc_with_acroform_field("common"), b)

    util = PDFMergerUtility()
    util.set_document_merge_mode(DocumentMergeMode.OPTIMIZE_RESOURCES_MODE)
    util.add_sources([str(a), str(b)])
    util.set_destination_file_name(str(out))
    util.merge_documents()

    with PDDocument.load(str(out)) as merged:
        form = merged.get_document_catalog().get_acro_form()
        assert form is not None
        names = sorted(f.get_partial_name() for f in form.get_fields())
        assert "common" in names
        assert any(
            n is not None and n.startswith("dummyFieldName") for n in names
        )


# ---------- annotation /Parent fix-up via import_page ----------


def test_wave1289_import_page_promotes_widget_annot_to_destination_acroform(
    tmp_path: Path,
) -> None:
    """When a page with a widget annotation pointing into the source
    AcroForm is imported, its top-level field root must end up in the
    destination document's /AcroForm /Fields so widget references stay
    navigable from the destination's form."""
    src = PDDocument()
    page = PDPage()
    _seed_page_contents(page)

    # Source AcroForm with a single text field plus widget on page.
    field_dict = COSDictionary()
    field_dict.set_name("FT", "Tx")
    field_dict.set_string(_T, "imported_widget")

    widget = COSDictionary()
    widget.set_name("Type", "Annot")
    widget.set_name("Subtype", "Widget")
    widget.set_item(_PARENT, field_dict)

    annots = COSArray()
    annots.add(widget)
    page.get_cos_object().set_item(_ANNOTS, annots)

    field_array = COSArray()
    field_array.add(field_dict)
    source_form = COSDictionary()
    source_form.set_item(_FIELDS, field_array)
    src.add_page(page)
    src.get_document_catalog().get_cos_object().set_item(_ACRO_FORM, source_form)

    try:
        dest = PDDocument()
        try:
            new_page = dest.import_page(src.get_page(0))
            new_form = dest.get_document_catalog().get_acro_form()
            assert new_form is not None
            names = [f.get_partial_name() for f in new_form.get_fields()]
            assert "imported_widget" in names
            # The widget annotation's /Parent must point at one of the
            # fields actually held under destination's /AcroForm /Fields.
            new_annots = new_page.get_cos_object().get_dictionary_object(
                _ANNOTS
            )
            assert isinstance(new_annots, COSArray)
            new_widget = new_annots.get_object(0)
            assert isinstance(new_widget, COSDictionary)
            new_parent = new_widget.get_dictionary_object(_PARENT)
            assert isinstance(new_parent, COSDictionary)
            dest_fields = (
                dest.get_document_catalog()
                .get_acro_form()
                .get_cos_object()
                .get_dictionary_object(_FIELDS)
            )
            assert isinstance(dest_fields, COSArray)
            field_id_set = {
                id(dest_fields.get_object(i))
                for i in range(dest_fields.size())
            }
            assert id(new_parent) in field_id_set
        finally:
            dest.close()
    finally:
        src.close()


def test_wave1289_import_page_acroform_collision_uniquifies_field_name() -> None:
    """If a same-named field already exists in the destination
    /AcroForm /Fields, the imported field must be renamed with a
    dummyFieldName prefix per the merger's collision-handling rule."""
    src = PDDocument()
    src_page = PDPage()
    _seed_page_contents(src_page)
    field_dict = COSDictionary()
    field_dict.set_name("FT", "Tx")
    field_dict.set_string(_T, "shared")
    widget = COSDictionary()
    widget.set_name("Type", "Annot")
    widget.set_name("Subtype", "Widget")
    widget.set_item(_PARENT, field_dict)
    annots = COSArray()
    annots.add(widget)
    src_page.get_cos_object().set_item(_ANNOTS, annots)
    src_form = COSDictionary()
    field_array = COSArray()
    field_array.add(field_dict)
    src_form.set_item(_FIELDS, field_array)
    src.add_page(src_page)
    src.get_document_catalog().get_cos_object().set_item(_ACRO_FORM, src_form)

    try:
        dest = PDDocument()
        try:
            # Pre-seed destination with a same-named field.
            existing = COSDictionary()
            existing.set_name("FT", "Tx")
            existing.set_string(_T, "shared")
            dest_form = COSDictionary()
            dest_fields = COSArray()
            dest_fields.add(existing)
            dest_form.set_item(_FIELDS, dest_fields)
            dest.get_document_catalog().get_cos_object().set_item(
                _ACRO_FORM, dest_form
            )

            dest.import_page(src.get_page(0))
            form = dest.get_document_catalog().get_acro_form()
            names = sorted(f.get_partial_name() for f in form.get_fields())
            assert names.count("shared") == 1
            assert any(
                n is not None and n.startswith("dummyFieldName")
                for n in names
            )
        finally:
            dest.close()
    finally:
        src.close()


def test_wave1289_import_page_without_widget_annots_leaves_acroform_alone() -> None:
    """A page with non-widget annotations or no annotations must not
    spawn a destination /AcroForm."""
    src = PDDocument()
    src_page = PDPage()
    _seed_page_contents(src_page)
    # Pure text annotation — not a widget.
    annot = COSDictionary()
    annot.set_name("Type", "Annot")
    annot.set_name("Subtype", "Text")
    annots = COSArray()
    annots.add(annot)
    src_page.get_cos_object().set_item(_ANNOTS, annots)
    src.add_page(src_page)

    try:
        dest = PDDocument()
        try:
            dest.import_page(src.get_page(0))
            form_obj = (
                dest.get_document_catalog()
                .get_cos_object()
                .get_dictionary_object(_ACRO_FORM)
            )
            # No AcroForm was needed — none should have been created.
            assert form_obj is None
        finally:
            dest.close()
    finally:
        src.close()


# ---------- legacy-mode regression (no behavioural change) ----------


def test_wave1289_legacy_mode_still_merges_two_documents(
    tmp_path: Path,
) -> None:
    """Legacy mode regression check — the existing default path stays
    functional."""
    a = tmp_path / "a.pdf"
    b = tmp_path / "b.pdf"
    out = tmp_path / "out.pdf"
    _save(_build_doc_with_font_resource(2), a)
    _save(_build_doc_with_font_resource(3), b)

    util = PDFMergerUtility()  # default is PDFBOX_LEGACY_MODE
    util.add_sources([str(a), str(b)])
    util.set_destination_file_name(str(out))
    util.merge_documents()

    with PDDocument.load(str(out)) as merged:
        assert merged.get_number_of_pages() == 5
