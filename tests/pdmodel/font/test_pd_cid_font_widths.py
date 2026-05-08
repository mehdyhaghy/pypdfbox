"""Tests for PDCIDFont width-table parsing (PDF 32000-1 §9.7.4.3)."""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSBase, COSFloat, COSInteger
from pypdfbox.pdmodel.font.pd_cid_font_type0 import PDCIDFontType0
from pypdfbox.pdmodel.font.pd_cid_font_type2 import PDCIDFontType2

# ---------- helpers ----------


def _arr(*values: int | float) -> COSArray:
    items: list[COSBase] = []
    for v in values:
        if isinstance(v, bool):  # bool is int subclass — guard explicitly
            raise TypeError("bool not supported in width array helper")
        if isinstance(v, int):
            items.append(COSInteger.get(v))
        else:
            items.append(COSFloat(v))
    return COSArray(items)


def _nested(*groups: int | float | list[int | float]) -> COSArray:
    """Build a /W array where ints/floats are scalars and lists are inner arrays."""
    items: list[COSBase] = []
    for g in groups:
        if isinstance(g, list):
            inner = COSArray()
            for x in g:
                if isinstance(x, int) and not isinstance(x, bool):
                    inner.add(COSInteger.get(x))
                else:
                    inner.add(COSFloat(float(x)))
            items.append(inner)
        elif isinstance(g, int) and not isinstance(g, bool):
            items.append(COSInteger.get(g))
        else:
            items.append(COSFloat(float(g)))
    arr = COSArray()
    for it in items:
        arr.add(it)
    return arr


# ---------- /DW (default width) ----------


def test_get_default_width_absent_returns_1000() -> None:
    font = PDCIDFontType0()
    assert font.get_default_width() == 1000.0


def test_get_default_width_round_trip() -> None:
    font = PDCIDFontType2()
    font.set_dw(750)
    assert font.get_default_width() == 750.0


def test_unmapped_cid_uses_dw() -> None:
    font = PDCIDFontType0()
    font.set_dw(750)
    # No /W set at all.
    assert font.get_glyph_width(42) == 750.0


# ---------- /W consecutive form: [c [w1 w2 ...]] ----------


def test_w_consecutive_form_assigns_successive_cids() -> None:
    font = PDCIDFontType0()
    # /W [3 [200 300 400]] -> width(3)=200, width(4)=300, width(5)=400
    font.set_w(_nested(3, [200, 300, 400]))
    assert font.get_glyph_width(3) == 200.0
    assert font.get_glyph_width(4) == 300.0
    assert font.get_glyph_width(5) == 400.0
    # CID 6 is unmapped -> /DW (default 1000).
    assert font.get_glyph_width(6) == 1000.0


def test_w_consecutive_form_with_floats() -> None:
    font = PDCIDFontType0()
    font.set_w(_nested(10, [123.5, 456.25]))
    widths = font.get_widths()
    assert widths[10] == 123.5
    assert widths[11] == 456.25


# ---------- /W range form: [c1 c2 w] ----------


def test_w_range_form_assigns_all_cids_inclusive() -> None:
    font = PDCIDFontType2()
    # /W [10 20 500] -> every CID 10..20 gets 500
    font.set_w(_nested(10, 20, 500))
    for cid in range(10, 21):
        assert font.get_glyph_width(cid) == 500.0
    # 21 outside range -> /DW
    assert font.get_glyph_width(21) == 1000.0
    # 9 outside range -> /DW
    assert font.get_glyph_width(9) == 1000.0


def test_w_range_form_endpoints_match_midpoint() -> None:
    font = PDCIDFontType0()
    font.set_w(_nested(10, 20, 500))
    assert font.get_glyph_width(10) == 500.0
    assert font.get_glyph_width(15) == 500.0
    assert font.get_glyph_width(20) == 500.0


# ---------- mixed forms in one array ----------


def test_w_mixed_consecutive_then_range() -> None:
    font = PDCIDFontType0()
    # /W [3 [200 300] 10 20 500]
    font.set_w(_nested(3, [200, 300], 10, 20, 500))
    assert font.get_glyph_width(3) == 200.0
    assert font.get_glyph_width(4) == 300.0
    # gap: CID 5..9 -> /DW
    assert font.get_glyph_width(5) == 1000.0
    assert font.get_glyph_width(9) == 1000.0
    # range: 10..20 -> 500
    assert font.get_glyph_width(10) == 500.0
    assert font.get_glyph_width(15) == 500.0
    assert font.get_glyph_width(20) == 500.0
    assert font.get_glyph_width(21) == 1000.0


def test_w_mixed_range_then_consecutive() -> None:
    font = PDCIDFontType0()
    # /W [10 20 500 100 [777 888]]
    font.set_w(_nested(10, 20, 500, 100, [777, 888]))
    assert font.get_glyph_width(10) == 500.0
    assert font.get_glyph_width(20) == 500.0
    assert font.get_glyph_width(100) == 777.0
    assert font.get_glyph_width(101) == 888.0


# ---------- empty / absent /W ----------


def test_empty_w_array_all_cids_use_dw() -> None:
    font = PDCIDFontType0()
    font.set_dw(444)
    font.set_w(COSArray())
    widths = font.get_widths()
    assert widths == {}
    assert font.get_glyph_width(0) == 444.0
    assert font.get_glyph_width(99999) == 444.0


def test_absent_w_array_all_cids_use_dw() -> None:
    font = PDCIDFontType0()
    font.set_dw(123)
    assert font.get_widths() == {}
    assert font.get_glyph_width(7) == 123.0


# ---------- caching behavior ----------


def test_widths_cache_returns_same_dict_instance() -> None:
    font = PDCIDFontType0()
    font.set_w(_nested(1, [100, 200]))
    a = font.get_widths()
    b = font.get_widths()
    assert a is b


def test_clear_widths_cache_reparses() -> None:
    font = PDCIDFontType0()
    font.set_w(_nested(1, [100, 200]))
    first = font.get_widths()
    assert first[1] == 100.0
    # Mutate: replace /W and clear cache.
    font.set_w(_nested(1, [999]))
    font.clear_widths_cache()
    second = font.get_widths()
    assert second is not first
    assert second[1] == 999.0


# ---------- /DW2 + /W2 vertical metrics ----------


def test_get_default_position_vector_absent_returns_spec_default() -> None:
    font = PDCIDFontType2()
    assert font.get_default_position_vector() == (880.0, -1000.0)


def test_get_default_position_vector_round_trip() -> None:
    font = PDCIDFontType2()
    font.set_dw2(_arr(900, -880))
    assert font.get_default_position_vector() == (900.0, -880.0)


def test_w2_consecutive_form_smoke() -> None:
    font = PDCIDFontType2()
    # /W2 [5 [880 -500 -1000]] -> CID 5 gets triple (880, -500, -1000)
    font.set_w2(_nested(5, [880, -500, -1000]))
    widths2 = font.get_widths2()
    assert widths2[5] == (880.0, -500.0, -1000.0)


def test_w2_range_form_smoke() -> None:
    font = PDCIDFontType2()
    # /W2 [10 12 880 -500 -1000] -> CIDs 10..12 share that triple
    font.set_w2(_nested(10, 12, 880, -500, -1000))
    widths2 = font.get_widths2()
    for cid in (10, 11, 12):
        assert widths2[cid] == (880.0, -500.0, -1000.0)
    assert 13 not in widths2


def test_wave329_w2_large_range_is_compact_but_still_lookupable() -> None:
    font = PDCIDFontType2()
    # /W2 [0 5000 880 -500 -1000] is range-form vertical metrics. It should
    # not materialize thousands of identical dict entries just to answer lookups.
    font.set_w2(_nested(0, 5000, 880, -500, -1000))

    assert font.get_widths2() == {}
    assert font.get_height(4999) == 880.0
    assert font.get_position_vector(4999) == (-500.0, -1000.0)
    assert font.get_vertical_displacement_vector_y(4999) == 880.0


def test_wave329_set_w2_none_clears_compact_range_cache() -> None:
    font = PDCIDFontType2()
    font.set_w2(_nested(0, 5000, 880, -500, -1000))
    assert font.get_position_vector(42) == (-500.0, -1000.0)

    font.set_w2(None)

    assert font.get_widths2() == {}
    assert font.get_position_vector(42) == (500.0, 880.0)
    assert font.get_vertical_displacement_vector_y(42) == -1000.0


def test_w2_consecutive_multi_triple() -> None:
    font = PDCIDFontType2()
    # /W2 [5 [880 -500 -1000  900 -510 -1010]] -> CID 5 + CID 6
    font.set_w2(_nested(5, [880, -500, -1000, 900, -510, -1010]))
    widths2 = font.get_widths2()
    assert widths2[5] == (880.0, -500.0, -1000.0)
    assert widths2[6] == (900.0, -510.0, -1010.0)


def test_w2_absent_returns_empty_dict() -> None:
    font = PDCIDFontType2()
    assert font.get_widths2() == {}
