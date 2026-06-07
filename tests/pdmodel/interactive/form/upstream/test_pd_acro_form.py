"""Upstream-derived tests for ``PDAcroForm``.

Translated from
``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/interactive/form/PDAcroFormTest.java``
(PDFBox 3.0). Tests requiring unported upstream features (full PDF load
+ render parity, PDFBox-3752 missing-DR auto-population, FDF export,
network-fetched fixture PDFs) are skipped with one-line comments.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSName
from pypdfbox.pdmodel.interactive.form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_text_field import PDTextField
from pypdfbox.pdmodel.pd_document import PDDocument


@pytest.fixture
def acro_form() -> tuple[PDDocument, PDAcroForm]:
    """Mirrors upstream ``@BeforeEach setUp``."""
    document = PDDocument()
    form = PDAcroForm(document)
    document.get_document_catalog().set_acro_form(form)
    return document, form


def test_fields_entry(acro_form: tuple[PDDocument, PDAcroForm]) -> None:
    """Upstream: ``testFieldsEntry``."""
    _, form = acro_form
    # the /Fields entry has been created with the AcroForm
    # as this is a required entry
    assert form.get_fields() is not None
    assert len(form.get_fields()) == 0

    # there shouldn't be an exception if there is no such field
    assert form.get_field("foo") is None

    # remove the required entry which is the case for some
    # PDFs (see PDFBOX-2965)
    form.get_cos_object().remove_item(COSName.get_pdf_name("Fields"))

    # ensure there is always an empty collection returned
    assert form.get_fields() is not None
    assert len(form.get_fields()) == 0

    # there shouldn't be an exception if there is no such field
    assert form.get_field("foo") is None


def test_acro_form_properties(acro_form: tuple[PDDocument, PDAcroForm]) -> None:
    """Upstream: ``testAcroFormProperties``."""
    _, form = acro_form
    assert form.get_default_appearance() == ""
    form.set_default_appearance("/Helv 0 Tf 0 g")
    assert form.get_default_appearance() == "/Helv 0 Tf 0 g"


# Skipped: ``testFlatten`` — needs ``Loader.loadPDF`` + the
# ``AlignmentTests.pdf`` fixture + the upstream ``TestPDFToImage``
# rendering harness. Replaced by hand-written ``test_pd_acro_form_flatten``.

# Skipped: ``testFlattenWidgetNoRef`` — same fixture/load dependencies
# as ``testFlatten``.

# ``testFlattenSpecificFieldsOnly`` — the upstream version loads
# ``AlignmentTests.pdf`` and asserts the count invariant
#   numFieldsBeforeFlatten == numFieldsAfterFlatten + fieldsToFlatten.size()
#   numWidgetsBeforeFlatten == numWidgetsAfterFlatten + fieldsToFlatten.size()
# after ``flatten(fieldsToFlatten, true)``. The bundled-fixture + render
# dependency is unported, but the *count invariant* itself is portable on a
# synthetic form (below). This is the load-bearing assertion the upstream
# test makes — that a partial flatten removes exactly the requested fields
# (and their widgets), no more, no fewer.


def test_flatten_specific_fields_only_count_invariant() -> None:
    """Port of ``testFlattenSpecificFieldsOnly`` count invariant: a partial
    ``flatten(fieldsToFlatten, ...)`` shrinks both the field set and the
    widget set by exactly ``len(fieldsToFlatten)``."""
    from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSStream
    from pypdfbox.pdmodel.pd_page import PDPage

    document = PDDocument()
    page = PDPage()
    document.add_page(page)
    form = PDAcroForm(document)
    document.get_document_catalog().set_acro_form(form)

    def _appearance() -> COSStream:
        stream = COSStream()
        stream.set_item(COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Form"))
        bbox = COSArray()
        for v in (0.0, 0.0, 50.0, 10.0):
            bbox.add(COSFloat(v))
        stream.set_item(COSName.get_pdf_name("BBox"), bbox)
        stream.set_raw_data(b"q Q\n")
        return stream

    annots = COSArray()
    fields: list[PDTextField] = []
    for i in range(5):
        field = PDTextField(form)
        field.set_partial_name(f"field{i}")
        cos = field.get_cos_object()
        cos.set_item(COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Widget"))
        rect = COSArray()
        for v in (10.0, 10.0 + i * 12.0, 60.0, 20.0 + i * 12.0):
            rect.add(COSFloat(v))
        cos.set_item(COSName.get_pdf_name("Rect"), rect)
        cos.set_item(COSName.get_pdf_name("P"), page.get_cos_object())
        ap = COSDictionary()
        ap.set_item(COSName.get_pdf_name("N"), _appearance())
        cos.set_item(COSName.get_pdf_name("AP"), ap)
        annots.add(cos)
        fields.append(field)
    page.get_cos_object().set_item(COSName.get_pdf_name("Annots"), annots)
    form.set_fields(fields)

    def _count_widgets() -> int:
        arr = page.get_cos_object().get_dictionary_object(COSName.get_pdf_name("Annots"))
        if not isinstance(arr, COSArray):
            return 0
        return sum(
            1
            for i in range(arr.size())
            if isinstance(arr.get_object(i), COSDictionary)
            and arr.get_object(i).get_dictionary_object(COSName.get_pdf_name("Subtype"))
            == COSName.get_pdf_name("Widget")
        )

    num_fields_before = len(form.get_fields())
    num_widgets_before = _count_widgets()

    fields_to_flatten = [form.get_field("field1"), form.get_field("field3")]
    form.flatten(fields_to_flatten, False)

    num_fields_after = len(form.get_fields())
    num_widgets_after = _count_widgets()

    assert num_fields_before == num_fields_after + len(fields_to_flatten)
    assert num_widgets_before == num_widgets_after + len(fields_to_flatten)
    # /AcroForm survives a partial flatten.
    assert document.get_document_catalog().get_acro_form() is not None
    document.close()

# Skipped: ``testDontAddMissingInformationOnDocumentLoad`` — exercises
# upstream PDFBOX-3752 lazy /DA + /DR auto-population on
# ``getDocumentCatalog().getAcroForm()``; we currently do not
# auto-populate, so this test would always pass trivially. Pinned in
# CHANGES.md.

# Skipped: ``testAddMissingInformationOnAcroFormAccess`` — same
# auto-population deferral as above.

# Skipped: ``testBadDA`` — depends on
# ``PDTextField.setValue`` raising ``IllegalArgumentException`` for a
# bad /DA string, which itself depends on full DA tokenisation.

# Skipped: ``testAcroFormDefaultFonts`` — exercises lazy
# /Helv + /ZaDb auto-add inside ``getAcroForm``.

# Skipped: ``testIllegalFieldsDefinition`` — requires fetching a
# remote PDF fixture (``Loader.loadPDF`` over HTTPS). Network test.

# Skipped: ``testPDFBox3347`` — same network-fetch dependency.

# Skipped: ``testPDFBox5797`` — needs ``PDType0Font.load`` from
# bundled TTF + ``setValue`` round-trip on a real PDF. Out of lite
# surface scope.


def test_acro_form_set_fields_round_trip(
    acro_form: tuple[PDDocument, PDAcroForm],
) -> None:
    """Hand-written supplement: round-trip ``set_fields`` + ``get_fields``
    with a typed text field. Mirrors the boilerplate every upstream test
    that uses ``PDTextField`` relies on (``setUp`` → add field →
    ``getFields().add(field)``)."""
    _, form = acro_form

    text_box = PDTextField(form)
    text_box.set_partial_name("SampleField")
    form.set_fields([text_box])

    fields = form.get_fields()
    assert len(fields) == 1
    assert fields[0].get_partial_name() == "SampleField"
    assert form.get_field("SampleField") is not None
