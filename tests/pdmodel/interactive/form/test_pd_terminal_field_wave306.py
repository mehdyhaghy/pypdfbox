from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSName
from pypdfbox.pdmodel.interactive.annotation import PDAnnotationWidget
from pypdfbox.pdmodel.interactive.form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_terminal_field import PDFieldStub

_KIDS: COSName = COSName.get_pdf_name("Kids")
_PARENT: COSName = COSName.get_pdf_name("Parent")


def test_set_widgets_rejects_self_parented_single_widget_dictionary() -> None:
    field = PDFieldStub(PDAcroForm())
    widget = PDAnnotationWidget(field.get_cos_object())

    with pytest.raises(ValueError, match="shares a dictionary"):
        field.set_widgets([widget])

    assert field.get_cos_object().get_dictionary_object(_KIDS) is None
    assert field.get_cos_object().get_dictionary_object(_PARENT) is None


def test_set_widgets_still_wires_distinct_widget_parent() -> None:
    field = PDFieldStub(PDAcroForm())
    widget = PDAnnotationWidget()

    field.set_widgets([widget])

    kids = field.get_cos_object().get_dictionary_object(_KIDS)
    assert isinstance(kids, COSArray)
    assert kids.get_object(0) is widget.get_cos_object()
    assert widget.get_parent() is field.get_cos_object()
