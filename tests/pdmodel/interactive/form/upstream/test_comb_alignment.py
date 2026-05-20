"""Upstream port of ``CombAlignmentTest``.

Source: ``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/interactive/form/CombAlignmentTest.java``
(PDFBox 3.0.x).

The upstream test is rendering-comparison driven (``TestPDFToImage``);
even on Java this is documented as "result must be viewed manually"
(line 66 / 91) — the rendering harness reports differences but does NOT
fail the test. Pypdfbox's lite port keeps the field-population half
and drops the rendering compare half.
"""

from __future__ import annotations

import pathlib

from pypdfbox.pdmodel import PDDocument

_FIXTURE_DIR = (
    pathlib.Path(__file__).resolve().parent.parent.parent.parent.parent
    / "fixtures"
    / "pdmodel"
    / "interactive"
    / "form"
)
_TEST_VALUE = "1234567"


def test_comb_fields() -> None:
    """Upstream: ``testCombFields`` (PDFBOX-5256)."""
    with PDDocument.load(_FIXTURE_DIR / "CombTest.pdf") as doc:
        acro_form = doc.get_document_catalog().get_acro_form()

        for name in ("PDFBoxCombLeft", "PDFBoxCombMiddle", "PDFBoxCombRight"):
            field = acro_form.get_field(name)
            field.set_value("")
            assert field.get_value() == ""
            field.set_value(_TEST_VALUE)
            assert field.get_value() == _TEST_VALUE


def test_pdf_box_5784() -> None:
    """Upstream: ``testPDFBOX5784``."""
    with PDDocument.load(_FIXTURE_DIR / "PDFBOX-5784.pdf") as doc:
        acro_form = doc.get_document_catalog().get_acro_form()

        for field in acro_form.get_field_tree():
            if "acrobat" not in field.get_partial_name():
                field.set_value("WIaqg")
                assert field.get_value() == "WIaqg"


# Skipped: upstream's ``TestPDFToImage.doTestFile`` rendering comparison
# step — non-fatal upstream and not in scope for the lite port.
