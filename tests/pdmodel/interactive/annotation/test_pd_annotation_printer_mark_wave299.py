from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName, COSString
from pypdfbox.pdmodel.interactive.annotation.pd_annotation import PDAnnotation
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_printer_mark import (
    PDAnnotationPrinterMark,
)


def test_wave299_printer_mark_upstream_mark_name_aliases_round_trip() -> None:
    ann = PDAnnotationPrinterMark()

    ann.setMarkName("RegistrationTarget")

    assert ann.getMarkName() == "RegistrationTarget"
    assert ann.get_mark_name() == "RegistrationTarget"
    raw = ann.get_cos_object().get_dictionary_object(COSName.get_pdf_name("MN"))
    assert isinstance(raw, COSString)
    assert raw.get_string() == "RegistrationTarget"


def test_wave299_printer_mark_alias_clear_removes_mn_entry() -> None:
    ann = PDAnnotationPrinterMark()
    ann.set_mark_name("ColorBar")

    ann.setMarkName(None)

    assert ann.get_mark_name() is None
    assert ann.getMarkName() is None
    assert not ann.get_cos_object().contains_key(COSName.get_pdf_name("MN"))


def test_wave299_printer_mark_factory_preserves_alias_surface() -> None:
    raw = COSDictionary()
    raw.set_name(COSName.SUBTYPE, PDAnnotationPrinterMark.SUB_TYPE)  # type: ignore[attr-defined]
    raw.set_string("MN", "CutMark")

    ann = PDAnnotation.create(raw)

    assert isinstance(ann, PDAnnotationPrinterMark)
    assert ann.getMarkName() == "CutMark"
