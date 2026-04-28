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

# Skipped: ``testFlattenSpecificFieldsOnly`` — requires
# ``AlignmentTests.pdf`` + ``refresh_appearances`` parity that depends
# on full /DA tokenisation.

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
