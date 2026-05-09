from __future__ import annotations

from pypdfbox.cos import COSFloat
from tests.pdmodel.font.test_pd_cid_font_wave618 import _num


def test_num_float_branch_returns_cos_float() -> None:
    number = _num(12.5)

    assert isinstance(number, COSFloat)
    assert number.float_value() == 12.5
