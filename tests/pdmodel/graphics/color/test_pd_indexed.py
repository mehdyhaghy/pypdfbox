from __future__ import annotations

from pypdfbox.cos import (
    COSArray,
    COSInteger,
    COSName,
    COSNull,
    COSStream,
    COSString,
)
from pypdfbox.pdmodel.graphics.color.pd_color import PDColor
from pypdfbox.pdmodel.graphics.color.pd_device_gray import PDDeviceGray
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


# ---------- default constructor ----------


def test_default_ctor_uses_device_rgb_hival_255_and_null_lookup() -> None:
    """The no-arg ctor mirrors upstream's default form:
    ``[/Indexed /DeviceRGB 255 null]``."""
    cs = PDIndexed()
    assert cs.get_name() == "Indexed"
    assert cs.NAME == "Indexed"
    assert cs.get_number_of_components() == 1
    base = cs.get_base_color_space()
    assert base is not None
    assert base.get_name() == "DeviceRGB"
    assert cs.get_hival() == 255
    assert cs.get_lookup_data() is None


def test_default_ctor_initial_color_is_zero_index_in_self() -> None:
    """``initial_color`` is the single-component PDColor ``[0]`` and its
    color space round-trips back to this PDIndexed instance."""
    cs = PDIndexed()
    initial = cs.get_initial_color()
    assert initial.get_components() == [0.0]
    assert initial.get_color_space() is cs


def test_initial_color_is_cached_singleton() -> None:
    """``get_initial_color`` returns the same object on every call —
    upstream caches it as a final field."""
    cs = PDIndexed()
    assert cs.get_initial_color() is cs.get_initial_color()


# ---------- /Decode default ----------


def test_default_decode_at_one_bit() -> None:
    """``[0, 1]`` for 1-bit images — 2 entries fit in two indices."""
    cs = PDIndexed()
    assert cs.get_default_decode(1) == [0.0, 1.0]


def test_default_decode_at_four_bits() -> None:
    """``[0, 15]`` for 4-bit images — 16 entries."""
    cs = PDIndexed()
    assert cs.get_default_decode(4) == [0.0, 15.0]


def test_default_decode_at_eight_bits() -> None:
    """``[0, 255]`` for 8-bit images — 256 entries."""
    cs = PDIndexed()
    assert cs.get_default_decode(8) == [0.0, 255.0]


def test_default_decode_independent_of_hival() -> None:
    """``/Decode`` default is the *index range* per BPC, not the hival —
    the two are independent quantities per PDF 32000-1 §8.9.5.1."""
    cs = _make_indexed(15, COSString(b"\x00" * 48))
    # hival=15 but bpc=8 still yields the full bpc range.
    assert cs.get_default_decode(8) == [0.0, 255.0]


# ---------- setters ----------


def test_set_hival_round_trip_via_getter() -> None:
    cs = PDIndexed()
    cs.set_hival(7)
    assert cs.get_hival() == 7
    cs.set_hival(0)
    assert cs.get_hival() == 0


def test_set_base_color_space_round_trip_via_getter() -> None:
    cs = PDIndexed()
    cs.set_base_color_space(PDDeviceGray.INSTANCE)
    base = cs.get_base_color_space()
    assert base is not None
    assert base.get_name() == "DeviceGray"


def test_set_lookup_data_with_bytes_round_trip() -> None:
    """Replacing /Lookup with a ``bytes`` payload writes a COSString and
    the getter pads/truncates against ``(hival+1) * base_components``."""
    cs = _make_indexed(3, COSString(b"\x00" * 12))
    payload = bytes(range(12))
    cs.set_lookup_data(payload)
    out = cs.get_lookup_data()
    assert out == payload


def test_set_lookup_data_none_writes_cos_null_and_getter_returns_none() -> None:
    """Passing ``None`` to ``set_lookup_data`` writes ``COSNull.NULL`` —
    matches upstream's ``array.set(3, COSNull.NULL)`` semantics for the
    default constructor."""
    cs = _make_indexed(2, COSString(b"\x00\xff\x00\xff\x00\xff"))
    cs.set_lookup_data(None)
    assert cs.get_lookup_data() is None
    # Verify the array slot is COSNull (preserved as a placeholder, not
    # removed). ``get_object`` unwraps ``COSNull`` to ``None``, so probe
    # the raw slot via ``get`` instead.
    arr = cs.get_array()
    assert arr is not None
    assert arr.get(3) is COSNull.NULL
    assert arr.size() == 4


def test_set_hival_then_set_lookup_then_str_form() -> None:
    """End-to-end: build via the no-arg ctor, populate hival + lookup
    via setters, and confirm the ``__str__`` reflects the new state."""
    cs = PDIndexed()
    cs.set_hival(3)
    cs.set_lookup_data(bytes(range(12)))
    assert str(cs) == "Indexed{base:DeviceRGB hival:3 lookup:(4 entries)}"


# ---------- __str__ form ----------


def test_str_default_constructor_form() -> None:
    """Default ctor: hival=255, lookup is COSNull → ``0 entries``."""
    cs = PDIndexed()
    assert str(cs) == "Indexed{base:DeviceRGB hival:255 lookup:(0 entries)}"


def test_str_with_populated_lookup_reports_entry_count() -> None:
    cs = _make_indexed(2, COSString(b"\x00\xff\x00\xff\x00\xff"))
    # 6 bytes / 3 components = 2 full entries — but get_lookup_data clamps
    # to (hival+1)*base = 9 bytes (zero-pads), so 9/3 = 3 entries.
    assert str(cs) == "Indexed{base:DeviceRGB hival:2 lookup:(3 entries)}"


def test_str_with_unresolvable_base_color_space_reports_none() -> None:
    """When the base CS slot can't be resolved, the ``__str__`` falls
    back to ``base:None`` (and ``0 entries`` since arity is unknown)."""
    arr = COSArray()
    arr.add(COSName.get_pdf_name("Indexed"))
    arr.add(COSInteger.get(99))  # not a valid CS dispatch — None
    arr.add(COSInteger.get(2))
    arr.add(COSString(b"\x00\xff\x00\xff\x00\xff"))
    cs = PDIndexed(arr)
    assert cs.get_base_color_space() is None
    assert str(cs) == "Indexed{base:None hival:2 lookup:(0 entries)}"


# ---------- get_lookup_data edge cases ----------


def test_get_lookup_data_returns_none_for_unsupported_slot_type() -> None:
    """When ``/Lookup`` is neither COSString nor COSStream (a malformed
    PDF could put any COSBase here), ``get_lookup_data`` returns
    ``None`` rather than crashing — pypdfbox lenience matching upstream's
    "tolerate weird PDFs" stance."""
    arr = COSArray()
    arr.add(COSName.get_pdf_name("Indexed"))
    arr.add(PDDeviceRGB.INSTANCE.get_cos_object())
    arr.add(COSInteger.get(2))
    arr.add(COSInteger.get(42))  # unsupported slot type
    cs = PDIndexed(arr)
    assert cs.get_lookup_data() is None


def test_get_lookup_data_at_hival_zero_returns_one_entry() -> None:
    """``hival=0`` is valid (a one-entry palette) — the getter clamps
    to ``(0 + 1) * base = 3`` bytes for DeviceRGB."""
    cs = _make_indexed(0, COSString(b"\x80\x00\xff"))
    out = cs.get_lookup_data()
    assert out == b"\x80\x00\xff"
    assert len(out) == 3


def test_get_lookup_data_unresolvable_base_returns_raw_bytes() -> None:
    """When the base CS can't be resolved (no clamp target), the lookup
    bytes come through untouched — matches the ``base is None`` short
    circuit in :meth:`get_lookup_data`."""
    arr = COSArray()
    arr.add(COSName.get_pdf_name("Indexed"))
    arr.add(COSInteger.get(99))  # not a valid CS dispatch
    arr.add(COSInteger.get(2))
    raw = b"abcdefghij"  # 10 bytes — would normally be clamped
    arr.add(COSString(raw))
    cs = PDIndexed(arr)
    assert cs.get_base_color_space() is None
    assert cs.get_lookup_data() == raw
