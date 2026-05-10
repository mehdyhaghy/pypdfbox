"""Upstream-style behavior tests for ``PDIndexed``.

Apache PDFBox 3.0.x ships no dedicated ``PDIndexedTest.java`` — the
class is exercised indirectly through fixture rendering. These tests
codify the behaviour documented in
``org.apache.pdfbox.pdmodel.graphics.color.PDIndexed`` (line refs in
each test) so future re-syncs surface upstream behaviour drift.
"""
from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSInteger,
    COSName,
    COSString,
)
from pypdfbox.pdmodel.graphics.color.pd_color import PDColor
from pypdfbox.pdmodel.graphics.color.pd_device_gray import PDDeviceGray
from pypdfbox.pdmodel.graphics.color.pd_device_rgb import PDDeviceRGB
from pypdfbox.pdmodel.graphics.color.pd_indexed import PDIndexed


def _indexed_rgb(hival: int, palette: bytes) -> PDIndexed:
    arr = COSArray()
    arr.add(COSName.get_pdf_name("Indexed"))
    arr.add(PDDeviceRGB.INSTANCE.get_cos_object())
    arr.add(COSInteger.get(hival))
    arr.add(COSString(palette))
    return PDIndexed(arr)


# ---------- to_rgb (PDIndexed.java line 173) ----------


def test_to_rgb_returns_palette_entry_at_index() -> None:
    # palette: black, red, green, blue
    palette = b"\x00\x00\x00\xff\x00\x00\x00\xff\x00\x00\x00\xff"
    cs = _indexed_rgb(3, palette)
    assert cs.to_rgb([0.0]) == [0.0, 0.0, 0.0]
    assert cs.to_rgb([1.0]) == [1.0, 0.0, 0.0]
    assert cs.to_rgb([2.0]) == [0.0, 1.0, 0.0]
    assert cs.to_rgb([3.0]) == [0.0, 0.0, 1.0]


def test_to_rgb_clamps_negative_index_to_zero() -> None:
    # Upstream: `index = Math.max(index, 0)` (line 183).
    palette = b"\x80\x80\x80\xff\x00\x00"
    cs = _indexed_rgb(1, palette)
    rgb = cs.to_rgb([-5.0])
    # Index 0 → 0x80/255 ≈ 0.5019.
    assert rgb[0] == pytest.approx(128 / 255.0, abs=1e-6)
    assert rgb[1] == pytest.approx(128 / 255.0, abs=1e-6)
    assert rgb[2] == pytest.approx(128 / 255.0, abs=1e-6)


def test_to_rgb_clamps_index_above_actual_max() -> None:
    # Upstream: `index = Math.min(index, actualMaxIndex)` (line 184).
    palette = b"\xff\x00\x00\x00\xff\x00"
    cs = _indexed_rgb(1, palette)
    # Out-of-range index falls back to the last entry.
    assert cs.to_rgb([99.0]) == [0.0, 1.0, 0.0]


def test_to_rgb_rounds_fractional_index() -> None:
    # Upstream: `Math.round(value[0])` (line 182) — banker's-or-half-up
    # behaviour. We use `int(round(...))` which matches half-to-even on
    # CPython for whole-half cases; the test picks a clear midpoint
    # so the choice doesn't matter.
    palette = b"\x00\x00\x00\xff\x00\x00\x00\xff\x00"
    cs = _indexed_rgb(2, palette)
    # 1.4 rounds to 1 → red.
    assert cs.to_rgb([1.4]) == [1.0, 0.0, 0.0]
    # 1.6 rounds to 2 → green.
    assert cs.to_rgb([1.6]) == [0.0, 1.0, 0.0]


def test_to_rgb_rejects_non_single_component_input() -> None:
    # Upstream: `IllegalArgumentException` (line 178).
    cs = _indexed_rgb(1, b"\x00\x00\x00\xff\xff\xff")
    with pytest.raises(ValueError):
        cs.to_rgb([0.0, 1.0])
    with pytest.raises(ValueError):
        cs.to_rgb([])


# ---------- to_rgb_image (PDIndexed.java line 194) ----------


def test_to_rgb_image_decodes_indexed_raster() -> None:
    # 2x2 image with indices {0,1,2,3} and a 4-entry palette.
    palette = b"\x00\x00\x00\xff\x00\x00\x00\xff\x00\x00\x00\xff"
    cs = _indexed_rgb(3, palette)
    img = cs.to_rgb_image(b"\x00\x01\x02\x03", 2, 2)
    assert img.mode == "RGB"
    assert img.size == (2, 2)
    assert list(img.getdata()) == [
        (0, 0, 0),
        (255, 0, 0),
        (0, 255, 0),
        (0, 0, 255),
    ]


def test_to_rgb_image_clamps_out_of_range_indices() -> None:
    # Upstream: `index = Math.min(src[x], actualMaxIndex)` (line 211).
    # Palette has only 2 entries (hival=1) but the raster pokes index 5.
    palette = b"\xff\x00\x00\x00\xff\x00"
    cs = _indexed_rgb(1, palette)
    img = cs.to_rgb_image(b"\x00\x05", 2, 1)
    # Index 5 is clamped to actualMaxIndex=1 → green.
    assert list(img.getdata()) == [(255, 0, 0), (0, 255, 0)]


def test_to_rgb_image_pads_short_raster_with_zero() -> None:
    palette = b"\x00\x00\x00\xff\xff\xff"
    cs = _indexed_rgb(1, palette)
    # Caller asks for 4 pixels but supplies 2 bytes — remaining pixels
    # land on index 0 (black).
    img = cs.to_rgb_image(b"\x01\x01", 2, 2)
    assert list(img.getdata()) == [
        (255, 255, 255),
        (255, 255, 255),
        (0, 0, 0),
        (0, 0, 0),
    ]


# ---------- to_raw_image (PDIndexed.java line 219) ----------


def test_to_raw_image_returns_palette_decoded_rgb_image() -> None:
    # Upstream returns a `BufferedImage` backed by an `IndexColorModel`
    # for sRGB-compatible bases; pypdfbox returns the palette-decoded
    # RGB image (functionally equivalent — same pixels — without the
    # AWT detour). See `PDIndexed.to_raw_image` for the divergence
    # rationale.
    palette = b"\xff\x00\x00\x00\xff\x00\x00\x00\xff"
    cs = _indexed_rgb(2, palette)
    img = cs.to_raw_image(b"\x00\x01\x02\x00", 2, 2)
    assert img is not None
    assert img.mode == "RGB"
    assert img.size == (2, 2)
    assert list(img.getdata()) == [
        (255, 0, 0),
        (0, 255, 0),
        (0, 0, 255),
        (255, 0, 0),
    ]


def test_to_raw_image_for_device_gray_base_returns_decoded_rgb() -> None:
    # Upstream returns null for non-sRGB-ICCBased bases; pypdfbox stays
    # consistent and palette-decodes for every base CS so callers
    # always see a usable Pillow image.
    arr = COSArray()
    arr.add(COSName.get_pdf_name("Indexed"))
    arr.add(PDDeviceGray.INSTANCE.get_cos_object())
    arr.add(COSInteger.get(2))
    arr.add(COSString(b"\x00\x80\xff"))
    cs = PDIndexed(arr)
    img = cs.to_raw_image(b"\x00\x01\x02", 3, 1)
    assert img is not None
    assert img.mode == "RGB"
    # Gray 0x00, 0x80, 0xff replicated to all three channels.
    pixels = list(img.getdata())
    assert pixels[0] == (0, 0, 0)
    assert pixels[2] == (255, 255, 255)
    assert pixels[1][0] == pixels[1][1] == pixels[1][2]


# ---------- get_initial_color (PDIndexed.java line 119) ----------


def test_get_initial_color_is_zero_index_pd_color() -> None:
    cs = PDIndexed()
    initial = cs.get_initial_color()
    assert initial.get_components() == [0.0]
    assert initial.get_color_space() is cs


# ---------- get_default_decode (PDIndexed.java line 113) ----------


def test_get_default_decode_at_eight_bits_is_zero_to_two_pow_n_minus_one() -> None:
    # Upstream: `new float[] { 0, (float)Math.pow(2, bpc) - 1 }` (line 116).
    cs = PDIndexed()
    assert cs.get_default_decode(8) == [0.0, 255.0]
    assert cs.get_default_decode(4) == [0.0, 15.0]
    assert cs.get_default_decode(1) == [0.0, 1.0]


# ---------- get_name / get_number_of_components ----------


def test_get_name_returns_indexed() -> None:
    # Upstream: `COSName.INDEXED.getName()` (line 104).
    assert PDIndexed().get_name() == "Indexed"


def test_get_number_of_components_is_one() -> None:
    # Upstream: returns literal `1` (line 110).
    assert PDIndexed().get_number_of_components() == 1


# ---------- get_base_color_space (PDIndexed.java line 246) ----------


def test_get_base_color_space_round_trip_through_setter() -> None:
    cs = PDIndexed()
    cs.set_base_color_space(PDDeviceGray.INSTANCE)
    base = cs.get_base_color_space()
    assert base is not None
    assert base.get_name() == "DeviceGray"


# ---------- toString / __str__ (PDIndexed.java line 336) ----------


def test_to_string_mirrors_upstream_format() -> None:
    palette = b"\x00\x00\x00\xff\x00\x00"
    cs = _indexed_rgb(1, palette)
    assert str(cs) == "Indexed{base:DeviceRGB hival:1 lookup:(2 entries)}"


# ---------- integration: PDColor.to_rgb routes through PDIndexed.to_rgb ----------


def test_pd_color_to_rgb_matches_pd_indexed_to_rgb() -> None:
    # Sanity check: the two surfaces agree for a representative palette
    # — PDColor.to_rgb is the high-level API, PDIndexed.to_rgb is the
    # raw-float surface upstream exposes for renderers.
    palette = b"\xff\x00\x00\x00\xff\x00\x00\x00\xff"
    cs = _indexed_rgb(2, palette)
    for i in range(3):
        from_pd_color = PDColor([float(i)], cs).to_rgb()
        from_pd_indexed = cs.to_rgb([float(i)])
        assert tuple(from_pd_indexed) == from_pd_color


# ---------- cached fields (PDIndexed.java lines 51-55) ----------


def test_actual_max_index_clamps_against_short_lookup() -> None:
    # Upstream: `actualMaxIndex = lookupData.length / numComponents - 1`
    # (line 295) when the lookup is shorter than `(hival + 1) * n`.
    palette = b"\xff\xff\xff\x00\x80\x80"  # 2 RGB entries
    cs = _indexed_rgb(5, palette)
    assert cs.get_actual_max_index() == 1


def test_color_table_field_layout_matches_upstream_n_by_k() -> None:
    # Upstream: `colorTable = new float[maxIndex + 1][numComponents]`
    # (line 299). We mirror as `list[list[float]]`.
    palette = b"\x00\x80\xff" * 4  # 4 entries, 3 components each
    cs = _indexed_rgb(3, palette)
    table = cs.get_color_table()
    assert len(table) == 4
    assert all(len(row) == 3 for row in table)


def test_rgb_color_table_field_layout_matches_upstream_n_by_3() -> None:
    # Upstream: `rgbColorTable = new int[actualMaxIndex + 1][3]`
    # (line 161). Each row is exactly 3 ints regardless of base CS arity.
    arr = COSArray()
    arr.add(COSName.get_pdf_name("Indexed"))
    arr.add(PDDeviceGray.INSTANCE.get_cos_object())
    arr.add(COSInteger.get(2))
    arr.add(COSString(b"\x00\x80\xff"))
    cs = PDIndexed(arr)
    rgb = cs.get_rgb_color_table()
    assert len(rgb) == 3
    assert all(len(row) == 3 for row in rgb)
