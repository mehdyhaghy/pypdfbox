from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSName
from tests.pdmodel.graphics.color.test_pd_color_to_rgb import _make_type2_function


def test_make_type2_function_writes_optional_range() -> None:
    function = _make_type2_function([0.0], [1.0], range_=[0.0, 1.0])

    range_array = function.get_dictionary_object(COSName.get_pdf_name("Range"))

    assert isinstance(range_array, COSArray)
    assert range_array.to_float_array() == pytest.approx([0.0, 1.0])
