from __future__ import annotations

from types import SimpleNamespace

import pytest

from . import test_pd_cid_font_type2_wave559 as wave559


def test_wave907_type2_missing_glyph_table_head_and_key_error_paths() -> None:
    table = wave559._MissingGlyphTable()

    assert table["head"] == SimpleNamespace()
    with pytest.raises(KeyError, match="glyf"):
        table["glyf"]


def test_wave907_type2_broken_head_table_head_and_key_error_paths() -> None:
    table = wave559._BrokenHeadTable()

    assert table["head"] == SimpleNamespace(xMin=-10.0, yMin=-20.0)
    with pytest.raises(KeyError, match="hhea"):
        table["hhea"]


def test_wave907_stub_ttf_width_helpers() -> None:
    ttf = wave559._StubTTF(object())

    assert ttf.get_advance_width(0) == 0
    assert ttf.get_advance_width(3) == 500
    assert ttf.advance_widths == [0, 500]

