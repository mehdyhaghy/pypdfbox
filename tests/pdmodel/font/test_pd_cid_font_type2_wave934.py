from __future__ import annotations

from tests.pdmodel.font import test_pd_cid_font_type2_wave523 as wave523


def test_wave934_sparse_glyph_inner_getitem_raises_key_error() -> None:
    inner = wave523._SparseGlyphInner()

    assert "glyf" in inner
    assert "head" not in inner
    try:
        inner["glyf"]
    except KeyError as exc:
        assert exc.args == ("glyf",)
    else:  # pragma: no cover - defensive assertion for helper behavior
        raise AssertionError("expected sparse glyph helper to raise KeyError")


def test_wave934_stub_ttf_metric_helpers_cover_both_width_paths() -> None:
    ttf = wave523._StubTTF(wave523._NoGlyphTableInner())

    assert ttf.get_advance_width(1) == 500
    assert ttf.get_advance_width(2) == 0
    assert ttf.advance_widths == [0, 500]
