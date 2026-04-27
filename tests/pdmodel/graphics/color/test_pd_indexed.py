from __future__ import annotations

from pypdfbox.cos import (
    COSArray,
    COSInteger,
    COSName,
    COSStream,
    COSString,
)
from pypdfbox.pdmodel.graphics.color.pd_color import PDColor
from pypdfbox.pdmodel.graphics.color.pd_device_rgb import PDDeviceRGB
from pypdfbox.pdmodel.graphics.color.pd_indexed import PDIndexed


def _make_indexed(hival: int, lookup_entry: COSString | COSStream) -> PDIndexed:
    arr = COSArray()
    arr.add(COSName.get_pdf_name("Indexed"))
    arr.add(PDDeviceRGB.INSTANCE.get_cos_object())
    arr.add(COSInteger.get(hival))
    arr.add(lookup_entry)
    return PDIndexed(arr)


# ---------- /Lookup as direct COSString ----------


def test_get_lookup_data_from_cos_string_round_trip() -> None:
    payload = bytes(range(0, 12))  # 4 entries * 3 components (DeviceRGB)
    cs = _make_indexed(3, COSString(payload))
    out = cs.get_lookup_data()
    assert out == payload
    assert len(out) == (3 + 1) * 3


# ---------- /Lookup as a /FlateDecode stream ----------


def test_get_lookup_data_from_flate_stream_decodes_through_filter() -> None:
    # 256 RGB entries — exactly the kind of palette that gets compressed
    # in the wild. Build a COSStream with /Filter /FlateDecode so the
    # raw body is *not* what the caller should see.
    palette = bytes(range(256)) * 3  # 768 bytes total, deterministic
    assert len(palette) == 768
    stream = COSStream()
    stream.set_data(palette, [COSName.FLATE_DECODE])  # type: ignore[attr-defined]

    # Sanity: raw bytes are compressed, not the plain palette.
    assert stream.to_raw_byte_array() != palette

    cs = _make_indexed(255, stream)
    out = cs.get_lookup_data()
    assert out == palette
    assert len(out) == (255 + 1) * 3


# ---------- defensive clamping ----------


def test_get_lookup_data_pads_short_payload_with_zero_bytes() -> None:
    # /Lookup carries only 6 bytes but hival=3 (DeviceRGB) needs 12.
    short = b"\x01\x02\x03\x04\x05\x06"
    cs = _make_indexed(3, COSString(short))
    out = cs.get_lookup_data()
    assert len(out) == 12
    assert out[: len(short)] == short
    assert out[len(short):] == b"\x00" * (12 - len(short))


def test_get_lookup_data_truncates_overlong_payload() -> None:
    # /Lookup is longer than (hival+1)*components — trim to the spec'd
    # length so palette indexing never walks past valid data.
    long = bytes(range(20))  # 20 bytes, expected 12
    cs = _make_indexed(3, COSString(long))
    out = cs.get_lookup_data()
    assert len(out) == 12
    assert out == long[:12]


# ---------- to_rgb integration through both /Lookup forms ----------


def test_pd_color_to_rgb_through_cos_string_lookup() -> None:
    # Index 1 should map to (255,0,0) → (1.0, 0.0, 0.0).
    palette = b"\x00\x00\x00\xff\x00\x00\x00\xff\x00"  # black, red, green
    cs = _make_indexed(2, COSString(palette))
    rgb = PDColor([1.0], cs).to_rgb()
    assert rgb == (1.0, 0.0, 0.0)


def test_pd_color_to_rgb_through_flate_stream_lookup() -> None:
    palette = b"\x00\x00\x00\xff\x00\x00\x00\xff\x00"  # black, red, green
    stream = COSStream()
    stream.set_data(palette, [COSName.FLATE_DECODE])  # type: ignore[attr-defined]
    cs = _make_indexed(2, stream)
    # Index 2 → green.
    rgb = PDColor([2.0], cs).to_rgb()
    assert rgb == (0.0, 1.0, 0.0)
