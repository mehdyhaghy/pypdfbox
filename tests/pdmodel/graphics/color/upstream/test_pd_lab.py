"""Ported parity tests for ``PDLab`` translated from upstream Apache
PDFBox 3.0.x ``PDLabTest.java``.

Upstream uses a single ``testLAB`` method that asserts default-read
non-mutation, then exercises ``setARange`` / ``setBRange`` /
``setWhitePoint`` / ``setBlackPoint`` and re-reads each. The pypdfbox
surface stores tristimulus + range as flat ``list[float]`` (no
``PDRange`` / ``PDTristimulus`` classes in the lite surface), so we
adapt the assertions to ``get_a_range()`` / ``get_b_range()`` /
``get_white_point()`` / ``get_black_point()``.
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary
from pypdfbox.pdmodel.graphics.color.pd_lab import PDLab


# Translated from PDLabTest.testLAB (PDLabTest.java line 39).
def test_lab_defaults_and_setters_round_trip() -> None:
    pd_lab = PDLab()
    cos_array = pd_lab.get_cos_object()
    assert isinstance(cos_array, COSArray)
    dict_entry = cos_array.get_object(1)
    assert isinstance(dict_entry, COSDictionary)

    # --- defaults: read-only operations must not mutate the dictionary ---
    assert pd_lab.get_name() == "Lab"
    assert pd_lab.get_number_of_components() == 3
    assert pd_lab.get_initial_color() is not None
    assert pd_lab.get_initial_color().get_components() == [0.0, 0.0, 0.0]
    bp = pd_lab.get_black_point()
    assert bp[0] == 0.0
    assert bp[1] == 0.0
    assert bp[2] == 0.0
    wp = pd_lab.get_white_point()
    assert wp[0] == 1.0
    assert wp[1] == 1.0
    assert wp[2] == 1.0
    a_range = pd_lab.get_a_range()
    assert a_range[0] == -100.0
    assert a_range[1] == 100.0
    b_range = pd_lab.get_b_range()
    assert b_range[0] == -100.0
    assert b_range[1] == 100.0
    assert dict_entry.size() == 0, (
        "read operations should not change the size of /Lab objects"
    )
    # rev 1571125 stack-overflow guard upstream: stringifying the
    # dictionary must not recurse through the parent array.
    str(dict_entry)

    # --- setters: round-trip a/b ranges, white point, black point ---
    pd_lab.set_a_range((-1.0, 2.0))
    pd_lab.set_b_range((3.0, 4.0))
    a_range = pd_lab.get_a_range()
    assert a_range[0] == -1.0
    assert a_range[1] == 2.0
    b_range = pd_lab.get_b_range()
    assert b_range[0] == 3.0
    assert b_range[1] == 4.0

    pd_lab.set_white_point([5.0, 6.0, 7.0])
    pd_lab.set_black_point([8.0, 9.0, 10.0])
    wp = pd_lab.get_white_point()
    assert wp[0] == 5.0
    assert wp[1] == 6.0
    assert wp[2] == 7.0
    bp = pd_lab.get_black_point()
    assert bp[0] == 8.0
    assert bp[1] == 9.0
    assert bp[2] == 10.0

    # Initial color recomputed from the new b-range minimum (>= 0).
    assert pd_lab.get_initial_color().get_components() == [0.0, 0.0, 3.0]


# ---------- private upstream helpers exposed for parity ----------


def test_get_default_range_array_returns_minus100_to_100_pairs() -> None:
    arr = PDLab.get_default_range_array()
    assert isinstance(arr, COSArray)
    assert arr.to_float_array() == [-100.0, 100.0, -100.0, 100.0]


def test_inverse_cube_branch_above_threshold() -> None:
    # 6/29 ≈ 0.2069; 0.5 > threshold → cubic branch.
    assert PDLab.inverse(0.5) == 0.5 ** 3


def test_inverse_linear_branch_at_or_below_threshold() -> None:
    # 6/29 is exactly at the threshold (uses else-branch in Java's
    # ``x > 6.0/29.0`` test). Linear value: (108/841)*(6/29 - 4/29).
    expected = (108.0 / 841.0) * ((6.0 / 29.0) - (4.0 / 29.0))
    assert PDLab.inverse(6.0 / 29.0) == expected


def test_set_component_range_array_writes_a_then_b() -> None:
    cs = PDLab()
    cs.set_component_range_array((-7.0, 7.0), 0)
    cs.set_component_range_array((-3.0, 3.0), 2)
    assert cs.get_a_range() == (-7.0, 7.0)
    assert cs.get_b_range() == (-3.0, 3.0)


def test_set_component_range_array_none_resets_to_default() -> None:
    cs = PDLab()
    cs.set_a_range((-5.0, 5.0))
    cs.set_component_range_array(None, 0)
    assert cs.get_a_range() == (-100.0, 100.0)


# ---------- to_rgb / to_rgb_image / to_raw_image upstream parity ----------


def test_to_rgb_at_lab_origin_matches_white_point() -> None:
    # L*=0 with neutral a/b under default white (1,1,1) is the deepest
    # black; the inverse(t) at t=16/116 hits the linear branch and
    # produces near-zero XYZ → near-zero sRGB.
    cs = PDLab()
    r, g, b = cs.to_rgb([0.0, 0.0, 0.0])
    assert 0.0 <= r <= 0.05
    assert 0.0 <= g <= 0.05
    assert 0.0 <= b <= 0.05


def test_to_rgb_neutral_l_100_uses_dictionary_white_point() -> None:
    cs = PDLab()
    cs.set_white_point([0.95047, 1.0, 1.08883])  # D65
    r, g, b = cs.to_rgb([100.0, 0.0, 0.0])
    # Pure-white Lab under D65 should drive sRGB toward (1, 1, 1).
    assert r > 0.95
    assert g > 0.95
    assert b > 0.95


def test_to_rgb_clamps_negative_xyz() -> None:
    # An extreme negative b* drives Z negative inside inverse(); the
    # convXYZtoRGB clamp should keep the channel finite (no NaN).
    cs = PDLab()
    r, g, b = cs.to_rgb([0.0, 0.0, -1000.0])
    for ch in (r, g, b):
        assert ch == ch  # not NaN
        assert 0.0 <= ch <= 1.0


def test_to_rgb_rejects_short_input() -> None:
    cs = PDLab()
    try:
        cs.to_rgb([0.0, 0.0])
    except ValueError:
        return
    raise AssertionError("expected ValueError for two-component input")


def test_to_raw_image_returns_none() -> None:
    # Upstream PDLab.toRawImage explicitly returns null.
    cs = PDLab()
    assert cs.to_raw_image(b"\x00\x80\xff" * 4, 2, 2) is None


def test_to_rgb_image_produces_rgb_pillow_image() -> None:
    # Tiny 1x1 raster with mid-grey L*, neutral a/b → produces a
    # finite RGB pixel (no exception, correct shape).
    cs = PDLab()
    img = cs.to_rgb_image(b"\x80\x80\x80", 1, 1)
    assert img.mode == "RGB"
    assert img.size == (1, 1)
    pixel = img.getpixel((0, 0))
    assert isinstance(pixel, tuple)
    assert len(pixel) == 3
    for ch in pixel:
        assert 0 <= ch <= 255


def test_to_rgb_image_pads_short_buffer() -> None:
    # Upstream operates on a WritableRaster sized to the image; the
    # pypdfbox port pads short buffers with zeros to keep the loop safe.
    cs = PDLab()
    img = cs.to_rgb_image(b"\xff\x80", 1, 1)  # 2 bytes, expects 3
    assert img.size == (1, 1)


# ---------- COS layout sanity ----------


def test_default_decode_uses_range_for_a_and_b() -> None:
    cs = PDLab()
    cs.set_a_range((-50.0, 50.0))
    cs.set_b_range((-30.0, 30.0))
    decode = cs.get_default_decode(8)
    assert decode == [0.0, 100.0, -50.0, 50.0, -30.0, 30.0]
