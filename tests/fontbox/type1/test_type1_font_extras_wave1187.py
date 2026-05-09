from __future__ import annotations

from tests.fontbox.type1 import test_type1_font_extras as extras


def test_wave1187_fake_t1_getitem_returns_font_entry() -> None:
    font = extras._make_font(font_name="Wave1187PS")

    assert font._t1["FontName"] == "Wave1187PS"
