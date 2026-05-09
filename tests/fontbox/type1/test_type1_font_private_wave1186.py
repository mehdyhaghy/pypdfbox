from __future__ import annotations

from tests.fontbox.type1.test_type1_font_private import _FakeT1


def test_wave1186_fake_t1_getitem_returns_font_entry() -> None:
    fake = _FakeT1({"FontName": "Wave1186"})

    assert fake["FontName"] == "Wave1186"
