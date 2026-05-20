"""Upstream port of ``AcroFormsRotationTest``.

Source: ``pdfbox/src/test/java/org/apache/pdfbox/
pdmodel/interactive/form/AcroFormsRotationTest.java`` (PDFBox 3.0.x).

The upstream test is rendering-comparison driven (``TestPDFToImage``);
even on Java this is documented as "result must be viewed manually"
(line 102) — the rendering harness reports differences but does NOT
fail the test. Pypdfbox's lite port keeps the field-population half
and drops the rendering compare half. We assert each field round-trips
its written value, which is a strict superset of what the upstream
non-fatal warning covers.
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
_NAME_OF_PDF = "AcroFormsRotation.pdf"
_TEST_VALUE = (
    "Lorem ipsum dolor sit amet, consetetur sadipscing elitr,"
    " sed diam nonumy eirmod tempor invidunt ut labore et dolore magna"
    " aliquyam erat, sed diam voluptua."
)


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

    # portrait page, single line fields
    for name in (
        "pdfbox.portrait.single.rotation0",
        "pdfbox.portrait.single.rotation90",
        "pdfbox.portrait.single.rotation180",
        "pdfbox.portrait.single.rotation270",
    ):
        field = acro_form.get_field(name)
        field.set_value(field.get_fully_qualified_name())
        assert field.get_value() == name

    # portrait page, multiline fields
    for name in (
        "pdfbox.portrait.multi.rotation0",
        "pdfbox.portrait.multi.rotation90",
        "pdfbox.portrait.multi.rotation180",
        "pdfbox.portrait.multi.rotation270",
    ):
        field = acro_form.get_field(name)
        field.set_value(field.get_fully_qualified_name() + "\n" + _TEST_VALUE)
        assert field.get_value() == name + "\n" + _TEST_VALUE

    # 90 degrees rotated page, single line fields
    for name in (
        "pdfbox.page90.single.rotation0",
        "pdfbox.page90.single.rotation90",
        "pdfbox.page90.single.rotation180",
        "pdfbox.page90.single.rotation270",
    ):
        field = acro_form.get_field(name)
        field.set_value(name)
        assert field.get_value() == name

    # 90 degrees rotated page, multiline fields
    for name in (
        "pdfbox.page90.multi.rotation0",
        "pdfbox.page90.multi.rotation90",
        "pdfbox.page90.multi.rotation180",
        "pdfbox.page90.multi.rotation270",
    ):
        field = acro_form.get_field(name)
        field.set_value(field.get_fully_qualified_name() + "\n" + _TEST_VALUE)
        assert field.get_value() == name + "\n" + _TEST_VALUE


# Skipped: upstream's ``TestPDFToImage.doTestFile`` rendering comparison
# step. Upstream itself logs a warning rather than failing when rendering
# differs, so this slice is non-load-bearing.
