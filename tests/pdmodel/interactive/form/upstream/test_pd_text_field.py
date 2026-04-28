"""Ported from upstream PDFBox 3.0 ``PDTextFieldTest``.

Source: ``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/interactive/form/PDTextFieldTest.java``
"""
from __future__ import annotations

import pytest

from pypdfbox.cos import COSName
from pypdfbox.pdmodel.interactive.form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_text_field import PDTextField

_FT: COSName = COSName.get_pdf_name("FT")


@pytest.fixture
def acro_form() -> PDAcroForm:
    return PDAcroForm()


def test_create_default_text_field(acro_form: PDAcroForm) -> None:
    """Upstream: ``createDefaultTextField`` — ``/FT`` is ``"Tx"`` and matches
    ``getFieldType``."""
    text_field = PDTextField(acro_form)
    assert text_field.get_field_type() == text_field.get_cos_object().get_name(_FT)
    assert text_field.get_field_type() == "Tx"


def test_create_widget_for_get(acro_form: PDAcroForm) -> None:
    """Upstream: ``createWidgetForGet`` — when ``/Type`` and ``/Subtype`` are
    absent, ``get_widgets()`` returns one merged widget over the field
    dictionary itself.

    Note: upstream auto-promotes the field dict to a widget by writing
    ``/Type /Annot`` and ``/Subtype /Widget`` on first ``getWidgets`` call.
    Our lite port returns the merged-widget shortcut directly without that
    side-effect; the deviation is recorded in ``CHANGES.md``.
    """
    text_field = PDTextField(acro_form)
    widget = text_field.get_widgets()[0]
    assert widget.get_cos_object() is text_field.get_cos_object()
