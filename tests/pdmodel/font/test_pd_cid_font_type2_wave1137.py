from __future__ import annotations

from tests.pdmodel.font.test_pd_cid_font_type2 import _StubTTF


def test_stub_ttf_advance_width_uses_last_width_for_out_of_range_gid() -> None:
    stub = _StubTTF(
        units_per_em=1000,
        advance_widths=[250, 500, 750],
        glyph_order=[".notdef", "A", "B"],
        glyphs={},
    )

    assert stub.get_advance_width(99) == 750


def test_stub_ttf_advance_width_uses_zero_when_no_widths_exist() -> None:
    stub = _StubTTF(
        units_per_em=1000,
        advance_widths=[],
        glyph_order=[],
        glyphs={},
    )

    assert stub.get_advance_width(0) == 0
