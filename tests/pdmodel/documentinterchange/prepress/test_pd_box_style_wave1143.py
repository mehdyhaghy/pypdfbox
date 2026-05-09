from __future__ import annotations

from pypdfbox.cos import COSArray, COSInteger
from tests.pdmodel.documentinterchange.prepress.test_pd_box_style_wave276 import _array


def test_wave1143_array_helper_accepts_existing_cos_items() -> None:
    nested = COSArray()
    nested.add(COSInteger.get(8))

    result = _array(nested)

    assert result.size() == 1
    assert result.get_object(0) is nested
