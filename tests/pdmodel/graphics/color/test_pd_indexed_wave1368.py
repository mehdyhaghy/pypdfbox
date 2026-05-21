"""Wave 1368 round-out tests for ``pypdfbox.pdmodel.graphics.color.pd_indexed``.

Targets:

- ``PDIndexed.create(base, hival, lookup_data)`` static factory (added
  by upstream PDFBOX-6192, ported to pypdfbox in wave 1368)
- ``/Hival`` round-trip + clamping (0..255)
- ``/Lookup`` as both ``COSString`` (literal palette) and ``COSStream``
  (Flate-compressed palette)
- ``get_color_table`` / ``get_rgb_color_table`` / ``get_actual_max_index``
- palette validation (truncate-when-overflow, pad-when-short)
- ``to_rgb`` lookup with index clamping
- ``to_rgb_image`` Pillow palette dispatch
- cache invalidation on setters (hival / lookup / base)
"""

from __future__ import annotations

import zlib

import pytest

from pypdfbox.cos import (
    COSArray,
    COSInteger,
    COSName,
    COSStream,
    COSString,
)
from pypdfbox.pdmodel.graphics.color.pd_device_gray import PDDeviceGray
from pypdfbox.pdmodel.graphics.color.pd_device_rgb import PDDeviceRGB
from pypdfbox.pdmodel.graphics.color.pd_indexed import PDIndexed

# ---------- helpers ----------


def _indexed(
    hival: int,
    palette: bytes,
    base: object = None,
) -> PDIndexed:
    arr = COSArray()
    arr.add(COSName.get_pdf_name("Indexed"))
    base = base if base is not None else PDDeviceRGB.INSTANCE
    arr.add(base.get_cos_object())
    arr.add(COSInteger.get(hival))
    arr.add(COSString(palette))
    return PDIndexed(arr)


# ---------- PDIndexed.create factory ----------


def test_create_factory_round_trip() -> None:
    """Mirrors upstream PDFBOX-6192 testFactory — 6 RGB triples."""
    base = PDDeviceRGB.INSTANCE
    hival = 5
    palette = bytes.fromhex("AA1166112233000000FEDC014561FEDC34DA")
    cs = PDIndexed.create(base, hival, palette)
    assert cs.get_name() == "Indexed"
    assert cs.get_hival() == 5
    assert cs.get_base_color_space() is base
    # Lookup data should round-trip verbatim.
    data = cs.get_lookup_data()
    assert data is not None
    assert data == palette


def test_create_factory_rejects_null_base() -> None:
    with pytest.raises(ValueError, match="base must not be null"):
        PDIndexed.create(None, 0, b"\x00\x00\x00")


def test_create_factory_rejects_null_lookup_data() -> None:
    with pytest.raises(ValueError, match="lookupData must not be null"):
        PDIndexed.create(PDDeviceRGB.INSTANCE, 0, None)


def test_create_factory_rejects_negative_hival() -> None:
    with pytest.raises(ValueError, match="hival"):
        PDIndexed.create(PDDeviceRGB.INSTANCE, -1, b"\x00\x00\x00")


def test_create_factory_rejects_oversized_hival() -> None:
    with pytest.raises(ValueError, match="hival"):
        PDIndexed.create(PDDeviceRGB.INSTANCE, 256, b"\x00\x00\x00")


def test_create_factory_rejects_short_lookup_data() -> None:
    # hival=5 + RGB(3 components) → expected = 6*3 = 18 bytes; supply 5.
    with pytest.raises(ValueError, match="lookupData too short"):
        PDIndexed.create(PDDeviceRGB.INSTANCE, 5, b"\x00" * 5)


def test_create_factory_returns_indexed_array_form() -> None:
    cs = PDIndexed.create(PDDeviceRGB.INSTANCE, 1, b"\xff\x00\x00\x00\xff\x00")
    cos = cs.get_cos_object()
    assert isinstance(cos, COSArray)
    assert cos.size() == 4
    assert cos.get_object(0).get_name() == "Indexed"


# ---------- /Hival ----------


def test_hival_round_trip() -> None:
    cs = _indexed(15, b"\x00" * 48)
    assert cs.get_hival() == 15


def test_hival_clamped_to_255() -> None:
    """A hival > 255 is clamped on read (PDF spec maximum)."""
    cs = _indexed(300, b"\x00" * 256 * 3)
    assert cs.get_hival() == 255


def test_hival_negative_clamped_to_zero() -> None:
    cs = _indexed(-5, b"\x00" * 3)
    assert cs.get_hival() == 0


def test_set_hival_invalidates_cache() -> None:
    cs = _indexed(0, b"\xff\x00\x00")
    # Prime the cache by reading the RGB table.
    cs.get_rgb_color_table()
    assert cs._rgb_color_table_cache is not None
    cs.set_hival(1)
    assert cs._rgb_color_table_cache is None


def test_set_high_value_alias_dispatches_to_set_hival() -> None:
    cs = _indexed(0, b"\xff\x00\x00")
    cs.set_high_value(5)
    assert cs.get_hival() == 5


# ---------- /Lookup string vs stream ----------


def test_lookup_data_from_cos_string() -> None:
    cs = _indexed(1, b"\xff\x00\x00\x00\xff\x00")
    data = cs.get_lookup_data()
    assert data == b"\xff\x00\x00\x00\xff\x00"


def test_lookup_data_from_cos_stream_with_flate() -> None:
    """A /Lookup that's a Flate-encoded COSStream should yield decoded bytes."""
    palette = b"\xff\x00\x00\x00\xff\x00\x00\x00\xff"  # 3 RGB entries
    compressed = zlib.compress(palette)
    stream = COSStream()
    stream.set_item(
        COSName.get_pdf_name("Filter"), COSName.get_pdf_name("FlateDecode")
    )
    stream.set_int(COSName.get_pdf_name("Length"), len(compressed))
    # Write the raw filtered bytes.
    with stream.create_raw_output_stream() as src:
        src.write(compressed)
    arr = COSArray()
    arr.add(COSName.get_pdf_name("Indexed"))
    arr.add(PDDeviceRGB.INSTANCE.get_cos_object())
    arr.add(COSInteger.get(2))
    arr.add(stream)
    cs = PDIndexed(arr)
    data = cs.get_lookup_data()
    assert data == palette


def test_lookup_data_truncates_when_oversized() -> None:
    """Lookup longer than (hival+1)*components should be truncated."""
    cs = _indexed(0, b"\xff\x00\x00" + b"\xff\xff\xff" * 10)
    data = cs.get_lookup_data()
    # hival=0 + RGB(3 components) → expected = 3 bytes.
    assert data == b"\xff\x00\x00"


def test_lookup_data_pads_when_short() -> None:
    """Short lookup is right-padded with NULs."""
    cs = _indexed(2, b"\xff\x00")  # 2 bytes for 3 RGB entries (9 needed)
    data = cs.get_lookup_data()
    assert data == b"\xff\x00" + b"\x00" * 7


def test_set_lookup_data_round_trip_and_cache_invalidation() -> None:
    cs = _indexed(0, b"\xff\x00\x00")
    cs.get_rgb_color_table()  # prime the cache
    assert cs._rgb_color_table_cache is not None
    cs.set_lookup_data(b"\x00\xff\x00")
    assert cs._rgb_color_table_cache is None
    # Read returns the new palette.
    assert cs.get_lookup_data() == b"\x00\xff\x00"


def test_clear_lookup_data_returns_none_from_read() -> None:
    cs = _indexed(0, b"\xff\x00\x00")
    cs.clear_lookup_data()
    assert cs.has_lookup_data() is False
    assert cs.get_lookup_data() is None


# ---------- base color space ----------


def test_base_color_space_round_trip() -> None:
    cs = _indexed(0, b"\x00", base=PDDeviceGray.INSTANCE)
    assert cs.get_base_color_space() is PDDeviceGray.INSTANCE
    assert cs.has_base_color_space() is True


def test_set_base_color_space_invalidates_cache() -> None:
    cs = _indexed(0, b"\xff\x00\x00")
    cs.get_rgb_color_table()  # prime
    assert cs._rgb_color_table_cache is not None
    cs.set_base_color_space(PDDeviceGray.INSTANCE)
    assert cs._rgb_color_table_cache is None


# ---------- color-table reads ----------


def test_get_color_table_decodes_to_floats() -> None:
    cs = _indexed(1, b"\xff\x00\x00\x00\xff\x00")
    table = cs.get_color_table()
    assert len(table) == 2
    assert table[0] == [1.0, 0.0, 0.0]
    assert table[1] == [0.0, 1.0, 0.0]


def test_get_rgb_color_table_returns_byte_palette() -> None:
    cs = _indexed(1, b"\xff\x00\x00\x00\xff\x00")
    rgb = cs.get_rgb_color_table()
    assert rgb == [(255, 0, 0), (0, 255, 0)]


def test_get_actual_max_index_clamps_against_lookup_length() -> None:
    # hival=10 but lookup is only 6 bytes → max index = 6//3 - 1 = 1.
    cs = _indexed(10, b"\xff\x00\x00\x00\xff\x00")
    # The constructor's pad/truncate logic for get_lookup_data() expands
    # the buffer to (hival+1)*components, so the actual_max_index will
    # equal hival after padding. We're testing read_color_table here
    # directly, which works on read_lookup_data() (the raw, unpadded
    # bytes).
    # Pad bytes are zeros — they're real palette entries from the table's
    # perspective. The max index equals hival, padded with black.
    assert cs.get_actual_max_index() == 1


# ---------- to_rgb ----------


def test_to_rgb_returns_palette_entry() -> None:
    cs = _indexed(2, b"\xff\x00\x00\x00\xff\x00\x00\x00\xff")
    assert cs.to_rgb([0]) == [1.0, 0.0, 0.0]
    assert cs.to_rgb([1]) == [0.0, 1.0, 0.0]
    assert cs.to_rgb([2]) == [0.0, 0.0, 1.0]


def test_to_rgb_clamps_negative_index_to_zero() -> None:
    cs = _indexed(1, b"\xff\x00\x00\x00\xff\x00")
    assert cs.to_rgb([-5]) == [1.0, 0.0, 0.0]


def test_to_rgb_clamps_over_max_index_to_last() -> None:
    cs = _indexed(1, b"\xff\x00\x00\x00\xff\x00")
    assert cs.to_rgb([99]) == [0.0, 1.0, 0.0]


def test_to_rgb_rejects_multi_component_input() -> None:
    cs = _indexed(1, b"\xff\x00\x00\x00\xff\x00")
    with pytest.raises(ValueError, match="one color value"):
        cs.to_rgb([0.0, 0.5])


def test_to_rgb_empty_palette_returns_black() -> None:
    """A PDIndexed with no Lookup data should map every index to black."""
    cs = PDIndexed()  # default ctor: no /Lookup
    assert cs.to_rgb([0]) == [0.0, 0.0, 0.0]


# ---------- to_rgb_image ----------


def test_to_rgb_image_returns_pillow_rgb() -> None:
    cs = _indexed(2, b"\xff\x00\x00\x00\xff\x00\x00\x00\xff")
    # 4 pixels: indices 0, 1, 2, 0.
    img = cs.to_rgb_image(b"\x00\x01\x02\x00", 2, 2)
    assert img.size == (2, 2)
    assert img.mode == "RGB"
    pixels = list(img.getdata())
    assert pixels == [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 0, 0)]


def test_to_rgb_image_clamps_out_of_range_indices() -> None:
    """Indices > hival should be clamped to the last valid palette entry."""
    cs = _indexed(1, b"\xff\x00\x00\x00\xff\x00")
    img = cs.to_rgb_image(b"\x00\x05\x99\xfa", 4, 1)
    pixels = list(img.getdata())
    # Indices 5, 0x99, 0xfa all clamp to palette[1] = green.
    assert pixels == [(255, 0, 0), (0, 255, 0), (0, 255, 0), (0, 255, 0)]


def test_to_rgb_image_pads_short_raster_with_index_zero() -> None:
    cs = _indexed(1, b"\xff\x00\x00\x00\xff\x00")
    img = cs.to_rgb_image(b"\x01", 2, 1)  # 1 byte for a 2-pixel raster
    pixels = list(img.getdata())
    # Second pixel is padded with 0 → palette[0] = red.
    assert pixels == [(0, 255, 0), (255, 0, 0)]


# ---------- to_raw_image dispatches to to_rgb_image ----------


def test_to_raw_image_returns_decoded_rgb() -> None:
    cs = _indexed(1, b"\xff\x00\x00\x00\xff\x00")
    img = cs.to_raw_image(b"\x00\x01", 2, 1)
    assert img.mode == "RGB"


# ---------- default decode ----------


def test_default_decode_is_index_range_per_bits_per_component() -> None:
    cs = _indexed(255, b"\x00" * 256 * 3)
    # 8 bits per component → [0, 255]; 4 bits → [0, 15]; 1 bit → [0, 1].
    assert cs.get_default_decode(8) == [0.0, 255.0]
    assert cs.get_default_decode(4) == [0.0, 15.0]
    assert cs.get_default_decode(1) == [0.0, 1.0]


# ---------- string form ----------


def test_to_string_format_matches_upstream() -> None:
    cs = _indexed(1, b"\xff\x00\x00\x00\xff\x00")
    s = cs.to_string()
    assert "Indexed{" in s
    assert "base:DeviceRGB" in s
    assert "hival:1" in s
    assert "2 entries" in s
