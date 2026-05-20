"""Upstream port of ``TestFields``.

Source: ``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/interactive/form/TestFields.java``
(PDFBox 3.0.x).
"""

from __future__ import annotations

import pathlib

from pypdfbox.cos import COSName, COSStream, COSString
from pypdfbox.pdmodel import PDDocument
from pypdfbox.pdmodel.interactive.form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_text_field import PDTextField

_FIXTURE_DIR = (
    pathlib.Path(__file__).resolve().parent.parent.parent.parent.parent
    / "fixtures"
    / "pdmodel"
    / "interactive"
    / "form"
)
_BASIC_FIELDS_PDF = _FIXTURE_DIR / "AcroFormsBasicFields.pdf"


def test_flags() -> None:
    """Upstream: ``testFlags``."""
    with PDDocument() as doc:
        form = PDAcroForm(doc)
        text_box = PDTextField(form)

        # assert that default is false.
        assert not text_box.is_comb()

        # try setting and clearing a single field
        text_box.set_comb(True)
        assert text_box.is_comb()
        text_box.set_comb(False)
        assert not text_box.is_comb()

        # try setting and clearing multiple fields
        text_box.set_comb(True)
        text_box.set_do_not_scroll(True)
        assert text_box.is_comb()
        assert text_box.do_not_scroll()

        text_box.set_comb(False)
        text_box.set_do_not_scroll(False)
        assert not text_box.is_comb()
        assert not text_box.do_not_scroll()

        # assert that setting a field to false multiple times works
        text_box.set_comb(False)
        assert not text_box.is_comb()
        text_box.set_comb(False)
        assert not text_box.is_comb()

        # assert that setting a field to true multiple times works
        text_box.set_comb(True)
        assert text_box.is_comb()
        text_box.set_comb(True)
        assert text_box.is_comb()


def test_acro_forms_basic_fields() -> None:
    """Upstream: ``testAcroFormsBasicFields``."""
    with PDDocument.load(_BASIC_FIELDS_PDF) as doc:
        # get and assert that there is a form
        form = doc.get_document_catalog().get_acro_form()
        assert form is not None

        # assert that there is no value, set the field value and
        # ensure it has been set
        text_field = form.get_field("TextField")
        assert text_field.get_cos_object().get_item(COSName.get_pdf_name("V")) is None
        text_field.set_value("field value")
        assert (
            text_field.get_cos_object().get_item(COSName.get_pdf_name("V")) is not None
        )
        assert text_field.get_value() == "field value"

        # assert when setting to null the key has also been removed
        assert (
            text_field.get_cos_object().get_item(COSName.get_pdf_name("V")) is not None
        )
        text_field.set_value(None)
        assert text_field.get_cos_object().get_item(COSName.get_pdf_name("V")) is None

        # get the TextField with a DV entry
        text_field = form.get_field("TextField-DefaultValue")
        assert text_field is not None
        assert text_field.get_default_value() == "DefaultValue"
        dv_obj = text_field.get_cos_object().get_dictionary_object(
            COSName.get_pdf_name("DV")
        )
        assert isinstance(dv_obj, COSString)
        assert text_field.get_default_value() == dv_obj.get_string()
        assert text_field.get_default_appearance() == "/Helv 12 Tf 0 g"

        # get a rich text field with a DV entry
        text_field = form.get_field("RichTextField-DefaultValue")
        assert text_field is not None
        assert text_field.get_default_value() == "DefaultValue"
        dv_obj = text_field.get_cos_object().get_dictionary_object(
            COSName.get_pdf_name("DV")
        )
        assert isinstance(dv_obj, COSString)
        assert text_field.get_default_value() == dv_obj.get_string()
        assert text_field.get_value() == "DefaultValue"
        assert text_field.get_default_appearance() == "/Helv 12 Tf 0 g"
        assert (
            text_field.get_default_style_string()
            == "font: Helvetica,sans-serif 12.0pt; text-align:left; color:#000000 "
        )
        # do not test for the full content as this is a rather long xml string
        assert len(text_field.get_rich_text_value()) == 338

        # get a rich text field with a text stream for the value
        text_field = form.get_field("LongRichTextField")
        assert text_field is not None
        # COSStream values are valid /V entries
        v = text_field.get_cos_object().get_dictionary_object(
            COSName.get_pdf_name("V")
        )
        assert isinstance(v, COSStream)
        assert len(text_field.get_value()) == 145396


def test_widget_missing_rect() -> None:
    """Upstream: ``testWidgetMissingRect``."""
    with PDDocument.load(_BASIC_FIELDS_PDF) as doc:
        form = doc.get_document_catalog().get_acro_form()

        text_field = form.get_field("TextField-DefaultValue")
        widget = text_field.get_widgets()[0]

        # initially there is an Appearance Entry in the form
        assert (
            widget.get_cos_object().get_dictionary_object(COSName.get_pdf_name("AP"))
            is not None
        )
        widget.get_cos_object().remove_item(COSName.get_pdf_name("Rect"))
        text_field.set_value("field value", regenerate_appearance=True)

        # There shall be no appearance entry if there is no /Rect to
        # behave as Adobe Acrobat does
        assert (
            widget.get_cos_object().get_dictionary_object(COSName.get_pdf_name("AP"))
            is None
        )
