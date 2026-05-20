"""Upstream port of ``TestCheckBox``.

Source: ``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/interactive/form/TestCheckBox.java``
(PDFBox 3.0.x).
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.pdmodel import PDDocument
from pypdfbox.pdmodel.common import PDRectangle
from pypdfbox.pdmodel.graphics.color import PDColor, PDDeviceRGB
from pypdfbox.pdmodel.interactive.annotation import (
    PDAppearanceCharacteristicsDictionary,
    PDBorderStyleDictionary,
)
from pypdfbox.pdmodel.interactive.form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_check_box import PDCheckBox
from pypdfbox.pdmodel.pd_page import PDPage


def test_checkbox_pd_model() -> None:
    """Upstream: ``testCheckboxPDModel``."""
    with PDDocument() as doc:
        form = PDAcroForm(doc)
        check_box = PDCheckBox(form)

        # test that there are no nulls returned for an empty field
        # only specific methods are tested here
        assert check_box.get_export_values() is not None
        assert check_box.get_value() is not None

        # Test setting/getting option values - the dictionaries Opt entry
        options = ["Value01", "Value02"]
        check_box.set_export_values(options)

        opt_item = check_box.get_cos_object().get_item(COSName.get_pdf_name("Opt"))
        assert isinstance(opt_item, COSArray)

        # assert that the values have been correctly set
        assert (
            check_box.get_cos_object().get_item(COSName.get_pdf_name("Opt")) is not None
        )
        assert opt_item.size() == 2
        assert opt_item.get_string(0) == options[0]

        # assert that the values can be retrieved correctly
        retrieved_options = check_box.get_export_values()
        assert len(retrieved_options) == 2
        assert retrieved_options == options

        # assert that the Opt entry is removed
        check_box.set_export_values(None)
        assert check_box.get_cos_object().get_item(COSName.get_pdf_name("Opt")) is None
        # if there is no Opt entry an empty List shall be returned
        assert len(check_box.get_export_values()) == 0


def test_check_box_no_appearance() -> None:
    """Upstream: ``testCheckBoxNoAppearance`` (PDFBOX-4366)."""
    with PDDocument() as doc:
        page = PDPage()
        doc.add_page(page)
        acro_form = PDAcroForm(doc)
        acro_form.set_need_appearances(True)  # need this or it won't appear on Adobe Reader
        doc.get_document_catalog().set_acro_form(acro_form)
        fields = []
        check_box = PDCheckBox(acro_form)
        check_box.set_partial_name("checkbox")
        widget = check_box.get_widgets()[0]
        widget.set_rectangle(PDRectangle(50, 600, 100, 100))
        bs = PDBorderStyleDictionary()
        bs.set_style(PDBorderStyleDictionary.STYLE_SOLID)
        bs.set_width(1)
        acd = COSDictionary()
        ac = PDAppearanceCharacteristicsDictionary(acd)
        ac.set_background(PDColor([1.0, 1.0, 0.0], PDDeviceRGB.INSTANCE))
        ac.set_border_colour(PDColor([1.0, 0.0, 0.0], PDDeviceRGB.INSTANCE))
        ac.set_normal_caption("4")  # 4 is checkmark, 8 is cross
        widget.set_appearance_characteristics(ac)
        widget.set_border_style(bs)
        check_box.set_value("Off")
        fields.append(check_box)
        page.get_annotations().append(widget)
        acro_form.set_fields(fields)
        assert check_box.get_value() == "Off"
