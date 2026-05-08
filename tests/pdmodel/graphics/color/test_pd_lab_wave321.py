from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.pdmodel.graphics.color.pd_lab import PDLab


def test_wave321_set_b_range_pads_short_existing_range() -> None:
    arr = COSArray()
    arr.add(COSName.get_pdf_name("Lab"))
    params = COSDictionary()
    short_range = COSArray.of_cos_floats([-25.0, 25.0])
    params.set_item(COSName.get_pdf_name("Range"), short_range)
    arr.add(params)
    cs = PDLab(arr)

    cs.set_b_range((-10.0, 10.0))

    assert short_range.to_float_array() == [-25.0, 25.0, -10.0, 10.0]
    assert cs.get_a_range() == (-25.0, 25.0)
    assert cs.get_b_range() == (-10.0, 10.0)
