from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.interactive.annotation.pd_annotation import PDAnnotation
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_printer_mark import (
    PDAnnotationPrinterMark,
)


def test_wave299_printer_mark_factory_preserves_mark_name() -> None:
    raw = COSDictionary()
    raw.set_name(COSName.SUBTYPE, PDAnnotationPrinterMark.SUB_TYPE)  # type: ignore[attr-defined]
    raw.set_string("MN", "CutMark")

    ann = PDAnnotation.create(raw)

    assert isinstance(ann, PDAnnotationPrinterMark)
    assert ann.get_mark_name() == "CutMark"
