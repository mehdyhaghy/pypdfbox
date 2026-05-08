from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.pdmodel.interactive.form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_check_box import PDCheckBox

_AP: COSName = COSName.get_pdf_name("AP")
_KIDS: COSName = COSName.get_pdf_name("Kids")
_N: COSName = COSName.get_pdf_name("N")
_OFF: COSName = COSName.get_pdf_name("Off")


def _widget_with_on_state(on_value: str) -> COSDictionary:
    widget = COSDictionary()
    ap = COSDictionary()
    normal = COSDictionary()
    normal.set_item(COSName.get_pdf_name(on_value), COSDictionary())
    normal.set_item(_OFF, COSDictionary())
    ap.set_item(_N, normal)
    widget.set_item(_AP, ap)
    return widget


def test_check_box_get_on_value_skips_malformed_kids() -> None:
    form = PDAcroForm()
    cb = PDCheckBox(form)
    kids = COSArray()
    kids.add(COSName.get_pdf_name("NotAWidget"))
    kids.add(_widget_with_on_state("Accepted"))
    cb.get_cos_object().set_item(_KIDS, kids)

    assert cb.get_on_value() == "Accepted"
