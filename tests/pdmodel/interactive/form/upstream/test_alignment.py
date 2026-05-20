"""Upstream port of ``AlignmentTest``.

Source: ``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/interactive/form/AlignmentTest.java``
(PDFBox 3.0.x).

The upstream test is rendering-comparison driven (``TestPDFToImage``);
even on Java this is documented as "result must be viewed manually"
(line 110) — the rendering harness reports differences but does NOT
fail the test. Pypdfbox's lite port keeps the field-population half
and drops the rendering compare half.
"""

from __future__ import annotations

import pathlib

import pytest

from pypdfbox.pdmodel import PDDocument
from pypdfbox.pdmodel.interactive.form import PDAcroForm

_FIXTURE_DIR = (
    pathlib.Path(__file__).resolve().parent.parent.parent.parent.parent
    / "fixtures"
    / "pdmodel"
    / "interactive"
    / "form"
)
_NAME_OF_PDF = "AlignmentTests.pdf"
_TEST_VALUE = "sdfASDF1234äöü"


@pytest.fixture
def env() -> tuple[PDDocument, PDAcroForm]:
    """Mirror upstream ``@BeforeEach setUp``."""
    doc = PDDocument.load(_FIXTURE_DIR / _NAME_OF_PDF)
    acro_form = doc.get_document_catalog().get_acro_form()
    yield doc, acro_form
    doc.close()


def test_fill_fields(env) -> None:
    """Upstream: ``fillFields``."""
    _, acro_form = env

    for name in (
        "AlignLeft",
        "AlignLeft-Border_Small",
        "AlignLeft-Border_Medium",
        "AlignLeft-Border_Wide",
        "AlignLeft-Border_Wide_Clipped",
        "AlignLeft-Border_Small_Outside",
        "AlignMiddle",
        "AlignMiddle-Border_Small",
        "AlignMiddle-Border_Medium",
        "AlignMiddle-Border_Wide",
        "AlignMiddle-Border_Wide_Clipped",
        "AlignMiddle-Border_Medium_Outside",
        "AlignRight",
        "AlignRight-Border_Small",
        "AlignRight-Border_Medium",
        "AlignRight-Border_Wide",
        "AlignRight-Border_Wide_Clipped",
        "AlignRight-Border_Wide_Outside",
    ):
        field = acro_form.get_field(name)
        assert field is not None, f"missing field {name}"
        field.set_value(_TEST_VALUE)
        assert field.get_value() == _TEST_VALUE


# Skipped: upstream's ``TestPDFToImage.doTestFile`` rendering comparison
# step — non-fatal upstream and not in scope for the lite port.
