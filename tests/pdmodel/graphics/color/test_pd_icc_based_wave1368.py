"""Wave 1368 round-out tests for ``pypdfbox.pdmodel.graphics.color.pd_icc_based``.

Targets the synthetic-profile parsing surface:

- ``/N`` component-count guard and round-trip (1/3/4 + invalid)
- ``/Alternate`` fallback dispatch (explicit and inferred from /N)
- ``/Range`` domain validation + ``get_range_for_component`` defaulting
- Header-byte inspection: ``get_device_class``, ``get_color_space_signature``,
  ``get_pcs_signature``, ``get_color_space_type``
- ``is_srgb`` device-model detection (synthetic profile bytes only)
- ``ensure_display_profile`` perceptual → display class rewrite
- ``int_to_big_endian`` and ``is_s_rgb`` static helpers
- ``clamp_colors`` /Range-aware clamp
- ``fallback_to_alternate_color_space``
- ``check_array`` shape validation
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSFloat, COSName, COSStream
from pypdfbox.pdmodel.graphics.color.pd_color_space import PDColorSpace
from pypdfbox.pdmodel.graphics.color.pd_device_cmyk import PDDeviceCMYK
from pypdfbox.pdmodel.graphics.color.pd_device_gray import PDDeviceGray
from pypdfbox.pdmodel.graphics.color.pd_device_rgb import PDDeviceRGB
from pypdfbox.pdmodel.graphics.color.pd_icc_based import (
    TYPE_CMYK,
    TYPE_GRAY,
    TYPE_LAB,
    TYPE_RGB,
    TYPE_XYZ,
    PDICCBased,
)

# ---------- synthetic ICC profile builder ----------


def _make_icc_profile(
    *,
    device_class: bytes = b"mntr",
    color_space: bytes = b"RGB ",
    pcs: bytes = b"XYZ ",
    rendering_intent: int = 0,
    device_model: bytes = b"sRGB   ",
    size: int = 128,
) -> bytes:
    """Build a minimal synthetic 128-byte ICC profile header.

    Per ICC.1:2010 §7.2 table 15 (ICC profile header layout):

    - bytes 0..3:   profile size (uint32 big-endian)
    - bytes 4..7:   preferred CMM type
    - bytes 8..11:  profile version
    - bytes 12..15: device class signature (4 ASCII chars)
    - bytes 16..19: data colour space signature (4 ASCII chars)
    - bytes 20..23: PCS signature (4 ASCII chars)
    - bytes 64..67: rendering intent (uint32 big-endian)
    - bytes 84..91: device model signature (8 ASCII chars)
    """
    header = bytearray(size)
    # Total profile size (uint32 big-endian).
    header[0:4] = size.to_bytes(4, "big", signed=False)
    header[12:16] = device_class
    header[16:20] = color_space
    header[20:24] = pcs
    header[64:68] = rendering_intent.to_bytes(4, "big", signed=False)
    # Device model is 8 bytes long in the spec.
    model_bytes = (device_model + b"\x00" * 8)[:8]
    header[84:92] = model_bytes
    return bytes(header)


def _make_icc_based(
    profile_bytes: bytes,
    n: int = 3,
    range_array: list[float] | None = None,
    alternate: PDColorSpace | None = None,
) -> PDICCBased:
    stream = COSStream()
    stream.set_int(COSName.get_pdf_name("N"), n)
    if range_array is not None:
        arr = COSArray()
        for v in range_array:
            arr.add(COSFloat(v))
        stream.set_item(COSName.get_pdf_name("Range"), arr)
    if alternate is not None:
        stream.set_item(
            COSName.get_pdf_name("Alternate"), alternate.get_cos_object()
        )
    with stream.create_output_stream() as src:
        src.write(profile_bytes)
    arr = COSArray()
    arr.add(COSName.get_pdf_name("ICCBased"))
    arr.add(stream)
    return PDICCBased(arr)


# ---------- /N component count ----------


@pytest.mark.parametrize(
    ("n_components", "expected_signature"),
    [
        (1, "GRAY"),
        (3, "RGB "),
        (4, "CMYK"),
    ],
    ids=["n1-gray", "n3-rgb", "n4-cmyk"],
)
def test_n_components_round_trip(n_components: int, expected_signature: str) -> None:
    profile = _make_icc_profile(color_space=expected_signature.encode("ascii"))
    cs = _make_icc_based(profile, n=n_components)
    assert cs.get_n() == n_components
    assert cs.get_number_of_components() == n_components


def test_set_n_updates_stored_value() -> None:
    cs = _make_icc_based(_make_icc_profile(), n=3)
    cs.set_n(4)
    assert cs.get_n() == 4


def test_get_n_returns_zero_for_missing_stream() -> None:
    """An ICCBased whose array second slot is missing should report N=0."""
    arr = COSArray()
    arr.add(COSName.get_pdf_name("ICCBased"))
    arr.add(COSStream())  # empty stream, no /N
    cs = PDICCBased(arr)
    assert cs.get_n() == 0


# ---------- /Alternate fallback ----------


def test_alternate_round_trip_explicit() -> None:
    profile = _make_icc_profile(color_space=b"CMYK")
    cs = _make_icc_based(profile, n=4, alternate=PDDeviceCMYK.INSTANCE)
    assert cs.get_alternate() is PDDeviceCMYK.INSTANCE
    assert cs.has_alternate() is True


def test_fallback_to_alternate_uses_explicit_alternate_when_present() -> None:
    cs = _make_icc_based(
        _make_icc_profile(), n=3, alternate=PDDeviceCMYK.INSTANCE
    )
    fallback = cs.fallback_to_alternate_color_space()
    assert fallback is PDDeviceCMYK.INSTANCE


def test_fallback_to_alternate_infers_from_n1() -> None:
    cs = _make_icc_based(b"", n=1)
    assert cs.fallback_to_alternate_color_space() is PDDeviceGray.INSTANCE


def test_fallback_to_alternate_infers_from_n3() -> None:
    cs = _make_icc_based(b"", n=3)
    assert cs.fallback_to_alternate_color_space() is PDDeviceRGB.INSTANCE


def test_fallback_to_alternate_infers_from_n4() -> None:
    cs = _make_icc_based(b"", n=4)
    assert cs.fallback_to_alternate_color_space() is PDDeviceCMYK.INSTANCE


def test_fallback_to_alternate_returns_none_for_unsupported_n() -> None:
    cs = _make_icc_based(b"", n=5)
    assert cs.fallback_to_alternate_color_space() is None


def test_clear_alternate_removes_entry() -> None:
    cs = _make_icc_based(b"", n=3, alternate=PDDeviceRGB.INSTANCE)
    assert cs.has_alternate() is True
    cs.clear_alternate()
    assert cs.has_alternate() is False


# ---------- /Range domain validation ----------


def test_range_defaults_when_absent() -> None:
    cs = _make_icc_based(b"", n=3)
    assert cs.has_range() is False
    for i in range(3):
        assert cs.get_range_for_component(i) == (0.0, 1.0)


def test_range_round_trip_per_component() -> None:
    rng = [0.0, 1.0, -1.0, 2.0, -3.0, 4.0]
    cs = _make_icc_based(b"", n=3, range_array=rng)
    assert cs.has_range() is True
    assert cs.get_range_for_component(0) == (0.0, 1.0)
    assert cs.get_range_for_component(1) == (-1.0, 2.0)
    assert cs.get_range_for_component(2) == (-3.0, 4.0)


def test_range_too_short_falls_back_to_default() -> None:
    """A /Range array shorter than 2N is treated as absent for safety."""
    rng = [0.0, 0.5]  # only one pair for an N=3 profile
    cs = _make_icc_based(b"", n=3, range_array=rng)
    assert cs.get_range_for_component(0) == (0.0, 1.0)


def test_set_range_for_component_pads_intermediate_slots() -> None:
    cs = _make_icc_based(b"", n=3)
    cs.set_range_for_component(2, -5.0, 5.0)
    # Component 0 and 1 should be padded with the default (0, 1) pairs.
    assert cs.get_range_for_component(0) == (0.0, 1.0)
    assert cs.get_range_for_component(1) == (0.0, 1.0)
    assert cs.get_range_for_component(2) == (-5.0, 5.0)


def test_clear_range_returns_defaults() -> None:
    cs = _make_icc_based(b"", n=3, range_array=[0.0, 1.0, -1.0, 2.0, -3.0, 4.0])
    assert cs.has_range() is True
    cs.clear_range()
    assert cs.has_range() is False
    assert cs.get_range_for_component(0) == (0.0, 1.0)


def test_get_default_decode_reflects_range() -> None:
    rng = [0.0, 1.0, -2.0, 2.0, -3.0, 3.0]
    cs = _make_icc_based(b"", n=3, range_array=rng)
    assert cs.get_default_decode(8) == [0.0, 1.0, -2.0, 2.0, -3.0, 3.0]


# ---------- header signature parsing ----------


def test_get_device_class_from_synthetic_profile() -> None:
    profile = _make_icc_profile(device_class=b"prtr")
    cs = _make_icc_based(profile, n=4)
    assert cs.get_device_class() == "prtr"


def test_get_color_space_signature_from_synthetic_profile() -> None:
    profile = _make_icc_profile(color_space=b"Lab ")
    cs = _make_icc_based(profile, n=3)
    assert cs.get_color_space_signature() == "Lab "


def test_get_pcs_signature_from_synthetic_profile() -> None:
    profile = _make_icc_profile(pcs=b"Lab ")
    cs = _make_icc_based(profile, n=3)
    assert cs.get_pcs_signature() == "Lab "


def test_header_signature_returns_none_for_empty_profile() -> None:
    cs = _make_icc_based(b"", n=3)
    assert cs.get_device_class() is None
    assert cs.get_color_space_signature() is None
    assert cs.get_pcs_signature() is None


# ---------- get_color_space_type ----------


@pytest.mark.parametrize(
    ("signature", "expected_type"),
    [
        (b"XYZ ", TYPE_XYZ),
        (b"Lab ", TYPE_LAB),
        (b"RGB ", TYPE_RGB),
        (b"GRAY", TYPE_GRAY),
        (b"CMYK", TYPE_CMYK),
    ],
    ids=["xyz", "lab", "rgb", "gray", "cmyk"],
)
def test_get_color_space_type_from_header_signature(
    signature: bytes, expected_type: int
) -> None:
    profile = _make_icc_profile(color_space=signature)
    cs = _make_icc_based(profile, n=3)
    assert cs.get_color_space_type() == expected_type


def test_get_color_space_type_falls_back_to_n_inference() -> None:
    """A profile with no recognisable colour-space signature should infer
    from /N."""
    profile = _make_icc_profile(color_space=b"????")
    cs = _make_icc_based(profile, n=1)
    assert cs.get_color_space_type() == TYPE_GRAY
    cs.set_n(3)
    assert cs.get_color_space_type() == TYPE_RGB
    cs.set_n(4)
    assert cs.get_color_space_type() == TYPE_CMYK
    cs.set_n(5)
    assert cs.get_color_space_type() == -1


def test_get_color_space_type_empty_profile_uses_n_inference() -> None:
    """When the profile is too short to read the signature, /N decides."""
    cs = _make_icc_based(b"", n=4)
    assert cs.get_color_space_type() == TYPE_CMYK


# ---------- is_srgb / is_s_rgb ----------


def test_is_srgb_detects_synthetic_sRGB_marker() -> None:
    profile = _make_icc_profile(device_model=b"sRGB   ")
    cs = _make_icc_based(profile, n=3)
    assert cs.is_srgb() is True


def test_is_srgb_returns_false_for_non_sRGB_marker() -> None:
    profile = _make_icc_profile(device_model=b"Other  ")
    cs = _make_icc_based(profile, n=3)
    assert cs.is_srgb() is False


def test_is_srgb_with_device_rgb_alternate() -> None:
    """When the embedded profile is unreadable but alternate is DeviceRGB."""
    cs = _make_icc_based(b"", n=3, alternate=PDDeviceRGB.INSTANCE)
    assert cs.is_srgb() is True


def test_is_s_rgb_static_helper() -> None:
    profile = _make_icc_profile(device_model=b"sRGB   ")
    assert PDICCBased.is_s_rgb(profile) is True
    profile_other = _make_icc_profile(device_model=b"abc    ")
    assert PDICCBased.is_s_rgb(profile_other) is False
    # Short profile → False (not enough bytes for device-model field).
    assert PDICCBased.is_s_rgb(b"\x00" * 10) is False


# ---------- ensure_display_profile / int_to_big_endian ----------


def test_ensure_display_profile_rewrites_perceptual_input_to_mntr() -> None:
    profile = _make_icc_profile(device_class=b"scnr", rendering_intent=0)
    patched = PDICCBased.ensure_display_profile(profile)
    assert patched[12:16] == b"mntr"


def test_ensure_display_profile_keeps_non_perceptual_unchanged() -> None:
    """Non-perceptual rendering intents should NOT be rewritten."""
    profile = _make_icc_profile(device_class=b"prtr", rendering_intent=1)
    patched = PDICCBased.ensure_display_profile(profile)
    assert patched[12:16] == b"prtr"


def test_ensure_display_profile_keeps_existing_mntr_unchanged() -> None:
    profile = _make_icc_profile(device_class=b"mntr", rendering_intent=0)
    patched = PDICCBased.ensure_display_profile(profile)
    # Already display — should return the original bytes verbatim.
    assert patched is profile


def test_ensure_display_profile_short_profile_returned_unchanged() -> None:
    short = b"\x00" * 60
    assert PDICCBased.ensure_display_profile(short) is short


def test_int_to_big_endian_writes_four_bytes() -> None:
    buf = bytearray(8)
    PDICCBased.int_to_big_endian(0x6D6E7472, buf, 2)  # "mntr"
    assert buf[2:6] == b"mntr"


# ---------- check_array shape validation ----------


def test_check_array_rejects_short_array() -> None:
    arr = COSArray()
    arr.add(COSName.get_pdf_name("ICCBased"))
    with pytest.raises(OSError, match="must have two elements"):
        PDICCBased.check_array(arr)


def test_check_array_rejects_non_stream_at_slot_one() -> None:
    arr = COSArray()
    arr.add(COSName.get_pdf_name("ICCBased"))
    arr.add(COSName.get_pdf_name("NotAStream"))
    with pytest.raises(OSError, match="stream as second element"):
        PDICCBased.check_array(arr)


def test_check_array_accepts_valid_shape() -> None:
    arr = COSArray()
    arr.add(COSName.get_pdf_name("ICCBased"))
    arr.add(COSStream())
    PDICCBased.check_array(arr)  # Should not raise.


# ---------- clamp_colors ----------


def test_clamp_colors_respects_range() -> None:
    rng = [0.0, 1.0, -1.0, 2.0, -3.0, 3.0]
    cs = _make_icc_based(b"", n=3, range_array=rng)
    # In-range values pass through.
    assert cs.clamp_colors([0.5, 0.5, 0.5]) == [0.5, 0.5, 0.5]
    # Out-of-range values clamp to the per-component bounds.
    assert cs.clamp_colors([1.5, 3.0, -10.0]) == [1.0, 2.0, -3.0]
    assert cs.clamp_colors([-1.0, -5.0, 10.0]) == [0.0, -1.0, 3.0]


def test_clamp_colors_uses_default_range_when_absent() -> None:
    cs = _make_icc_based(b"", n=3)
    assert cs.clamp_colors([0.5, 1.2, -0.5]) == [0.5, 1.0, 0.0]


# ---------- load_icc_profile ----------


def test_load_icc_profile_returns_empty_for_no_profile() -> None:
    cs = _make_icc_based(b"", n=3)
    assert cs.load_icc_profile() == b""


def test_load_icc_profile_rewrites_scnr_to_mntr_on_perceptual() -> None:
    profile = _make_icc_profile(device_class=b"scnr", rendering_intent=0)
    cs = _make_icc_based(profile, n=3)
    out = cs.load_icc_profile()
    assert out[12:16] == b"mntr"


# ---------- string form ----------


def test_to_string_includes_component_count() -> None:
    cs = _make_icc_based(b"", n=4)
    assert cs.to_string() == "ICCBased{numberOfComponents: 4}"


# ---------- PDColorSpace.create dispatches to ICCBased ----------


def test_pdcolorspace_create_dispatches_icc_array_to_pdiccbased() -> None:
    profile = _make_icc_profile()
    cs = _make_icc_based(profile, n=3)
    arr = cs.get_cos_object()
    assert isinstance(arr, COSArray)
    dispatched = PDColorSpace.create(arr)
    assert isinstance(dispatched, PDICCBased)
    assert dispatched.get_n() == 3
