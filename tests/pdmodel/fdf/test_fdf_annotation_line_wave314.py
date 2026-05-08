from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName, COSObject
from pypdfbox.pdmodel.fdf import FDFAnnotationLine


def _float_ref(object_number: int, value: float) -> COSObject:
    return COSObject(object_number, resolved=COSFloat(value))


def test_wave314_line_points_resolve_indirect_numeric_entries() -> None:
    annot = COSDictionary()
    annot.set_item(
        COSName.get_pdf_name("L"),
        COSArray(
            [
                _float_ref(10, 1.25),
                _float_ref(11, 2.5),
                _float_ref(12, 3.75),
                _float_ref(13, 4.0),
            ]
        ),
    )

    line = FDFAnnotationLine(annot)

    assert line.get_start_point() == pytest.approx((1.25, 2.5), abs=1e-6)
    assert line.get_end_point() == pytest.approx((3.75, 4.0), abs=1e-6)


def test_wave314_caption_offsets_resolve_indirect_numeric_entries() -> None:
    annot = COSDictionary()
    annot.set_item(
        COSName.get_pdf_name("CO"),
        COSArray([_float_ref(20, -1.5), _float_ref(21, 2.25)]),
    )

    line = FDFAnnotationLine(annot)

    assert line.get_caption_horizontal_offset() == pytest.approx(-1.5, abs=1e-6)
    assert line.get_caption_vertical_offset() == pytest.approx(2.25, abs=1e-6)
