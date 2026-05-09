from __future__ import annotations

import pytest

from pypdfbox.pdmodel.font.pd_cid_font_type2 import PDCIDFontType2
from tests.pdmodel.font import test_pd_cid_font_type2_round_out as round_out


def test_round_out_stub_ttf_helpers_expose_duck_typed_surface() -> None:
    glyph = round_out._StubGlyph(1, 9)
    glyphs = {"A": glyph}
    inner = round_out._StubTTInner(["A"], glyphs, object())

    assert "glyf" in inner
    assert "cmap" not in inner
    assert inner["glyf"]["A"] is glyph
    assert inner.getGlyphOrder() == ["A"]
    assert inner.getGlyphName(0) == "A"
    assert inner.getGlyphSet()["A"] is glyph

    ttf = round_out._StubTTF(1000, ["A"], glyphs)
    assert ttf.get_advance_width(0) == 0
    assert ttf.advance_widths == []
    with pytest.raises(AttributeError, match="is_post_script not provided"):
        ttf.is_post_script()


def test_predicate_missing_stub_get_units_per_em_branch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def call_units_per_em_then_return_false(self: PDCIDFontType2) -> bool:
        font = self.get_true_type_font()
        assert font is not None
        assert font.get_units_per_em() == 1000
        return False

    monkeypatch.setattr(
        PDCIDFontType2,
        "is_open_type_post_script",
        call_units_per_em_then_return_false,
    )

    round_out.test_is_open_type_post_script_false_when_predicate_missing()
