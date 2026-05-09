from __future__ import annotations

import pytest

from . import test_pd_cid_font_widths as widths


def test_wave933_arr_helper_rejects_bool_and_accepts_float() -> None:
    with pytest.raises(TypeError, match="bool not supported"):
        widths._arr(True)

    arr = widths._arr(12.5)

    assert arr.size() == 1
    assert arr.get_object(0).float_value() == pytest.approx(12.5)


def test_wave933_nested_helper_accepts_top_level_float() -> None:
    arr = widths._nested(3.5)

    assert arr.size() == 1
    assert arr.get_object(0).float_value() == pytest.approx(3.5)
