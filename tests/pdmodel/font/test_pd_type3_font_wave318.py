from __future__ import annotations

import pytest

from pypdfbox.pdmodel.font.pd_type3_font import PDType3Font


def test_wave318_get_width_offsets_from_negative_first_char() -> None:
    font = PDType3Font()
    font.set_first_char(-1)
    font.set_last_char(1)
    font.set_widths([111.0, 222.0, 333.0])

    assert font.get_width(0) == pytest.approx(222.0)
    assert font.get_width(1) == pytest.approx(333.0)
