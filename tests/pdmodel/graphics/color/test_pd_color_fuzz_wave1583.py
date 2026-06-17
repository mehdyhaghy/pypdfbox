"""Fuzz / parity tests for ``PDColor`` (wave 1583).

Hammers the core ``PDColor`` value surface against upstream PDFBox 3.0.7
``org.apache.pdfbox.pdmodel.graphics.color.PDColor`` semantics:

- constructing from ``components + colorspace`` and ``COSName + colorspace``
- ``get_components`` returns a *defensive copy*, sized to the colour space
  arity (``Arrays.copyOf`` truncate/pad semantics)
- ``to_rgb`` delegating to the colour space (DeviceRGB identity, DeviceGray
  replication, DeviceCMYK conversion)
- ``get_pattern_name`` for pattern colours (and ``None`` for non-pattern)
- ``to_cos_array`` round-trip (components then trailing pattern name)
- equality / hashing over components + colour space + pattern name
- the immutability of the returned components and the empty / pattern-only
  forms

Upstream reference: ``PDColor.java`` (components.clone() / Arrays.copyOf,
toCOSArray = setFloatArray + optional patternName, getPatternName,
isPattern == patternName != null).
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSFloat, COSInteger, COSName
from pypdfbox.pdmodel.graphics.color.pd_color import PDColor
from pypdfbox.pdmodel.graphics.color.pd_device_cmyk import PDDeviceCMYK
from pypdfbox.pdmodel.graphics.color.pd_device_gray import PDDeviceGray
from pypdfbox.pdmodel.graphics.color.pd_device_rgb import PDDeviceRGB
from pypdfbox.pdmodel.graphics.color.pd_pattern import PDPattern

# ---------- construction: components + colorspace ----------


@pytest.mark.parametrize(
    "components",
    [
        [0.0, 0.0, 0.0],
        [1.0, 1.0, 1.0],
        [0.5, 0.25, 0.75],
        [0.1, 0.9, 0.333333],
    ],
    ids=["black", "white", "mid", "fractional"],
)
def test_construct_components_and_colorspace_rgb(
    components: list[float],
) -> None:
    color = PDColor(components, PDDeviceRGB.INSTANCE)
    assert color.get_components() == components
    assert color.get_color_space() is PDDeviceRGB.INSTANCE
    assert color.get_pattern_name() is None
    assert not color.is_pattern()


def test_construct_components_are_floats() -> None:
    # Integer inputs become floats (upstream stores a float[]).
    color = PDColor([0, 1, 0], PDDeviceRGB.INSTANCE)
    comps = color.get_components()
    assert comps == [0.0, 1.0, 0.0]
    assert all(isinstance(c, float) for c in comps)


def test_construct_gray_single_component() -> None:
    color = PDColor([0.42], PDDeviceGray.INSTANCE)
    assert color.get_components() == [0.42]
    assert color.get_color_space() is PDDeviceGray.INSTANCE


def test_construct_cmyk_four_components() -> None:
    color = PDColor([0.1, 0.2, 0.3, 0.4], PDDeviceCMYK.INSTANCE)
    assert color.get_components() == [0.1, 0.2, 0.3, 0.4]


# ---------- get_components: defensive copy + arity sizing ----------


def test_get_components_returns_defensive_copy() -> None:
    color = PDColor([0.5, 0.25, 0.75], PDDeviceRGB.INSTANCE)
    first = color.get_components()
    first[0] = 99.0
    # Mutating the returned list must not touch the internal state.
    assert color.get_components() == [0.5, 0.25, 0.75]


def test_get_components_distinct_lists_each_call() -> None:
    color = PDColor([0.5, 0.25, 0.75], PDDeviceRGB.INSTANCE)
    assert color.get_components() is not color.get_components()


def test_get_components_pads_short_array() -> None:
    # PDFBOX-4279: Arrays.copyOf right-pads with 0.0 to the CS arity.
    color = PDColor([0.5, 0.25], PDDeviceRGB.INSTANCE)
    assert color.get_components() == [0.5, 0.25, 0.0]


def test_get_components_truncates_long_array() -> None:
    color = PDColor([0.1, 0.2, 0.3, 0.4], PDDeviceRGB.INSTANCE)
    assert color.get_components() == [0.1, 0.2, 0.3]


def test_get_components_pattern_no_resize() -> None:
    # Pattern colour space: clone raw, no resize (upstream instanceof
    # PDPattern branch).
    pattern_cs = PDPattern(PDDeviceRGB.INSTANCE)
    name = COSName.get_pdf_name("P1")
    color = PDColor([0.5, 0.25, 0.75], name, pattern_cs)
    assert color.get_components() == [0.5, 0.25, 0.75]


# ---------- constructor argument source must not be aliased ----------


def test_constructor_copies_input_list() -> None:
    src = [0.5, 0.25, 0.75]
    color = PDColor(src, PDDeviceRGB.INSTANCE)
    src[0] = 99.0
    # Mutating the caller's list must not affect the colour.
    assert color.get_components() == [0.5, 0.25, 0.75]


# ---------- to_rgb: delegation per colour space ----------


@pytest.mark.parametrize(
    "rgb",
    [
        (0.0, 0.0, 0.0),
        (1.0, 1.0, 1.0),
        (0.25, 0.5, 0.75),
        (0.1, 0.2, 0.3),
    ],
    ids=["black", "white", "mid", "low"],
)
def test_to_rgb_devicergb_identity(rgb: tuple[float, float, float]) -> None:
    color = PDColor(list(rgb), PDDeviceRGB.INSTANCE)
    assert color.to_rgb() == pytest.approx(rgb)


@pytest.mark.parametrize("g", [0.0, 0.25, 0.5, 0.75, 1.0])
def test_to_rgb_devicegray_replicates(g: float) -> None:
    color = PDColor([g], PDDeviceGray.INSTANCE)
    assert color.to_rgb() == pytest.approx((g, g, g))


@pytest.mark.parametrize(
    ("cmyk", "expected"),
    [
        ((0.0, 0.0, 0.0, 0.0), (1.0, 1.0, 1.0)),  # all-zero CMYK -> white
        ((0.0, 0.0, 0.0, 1.0), (0.0, 0.0, 0.0)),  # K=1 -> black
        ((1.0, 0.0, 0.0, 0.0), (0.0, 1.0, 1.0)),  # cyan
        ((0.0, 1.0, 0.0, 0.0), (1.0, 0.0, 1.0)),  # magenta
        ((0.0, 0.0, 1.0, 0.0), (1.0, 1.0, 0.0)),  # yellow
    ],
    ids=["white", "black", "cyan", "magenta", "yellow"],
)
def test_to_rgb_devicecmyk(
    cmyk: tuple[float, float, float, float],
    expected: tuple[float, float, float],
) -> None:
    color = PDColor(list(cmyk), PDDeviceCMYK.INSTANCE)
    assert color.to_rgb() == pytest.approx(expected)


def test_to_rgb_clamps_out_of_range() -> None:
    color = PDColor([2.0, -1.0, 0.5], PDDeviceRGB.INSTANCE)
    assert color.to_rgb() == pytest.approx((1.0, 0.0, 0.5))


def test_to_rgb_int_packs_channels() -> None:
    color = PDColor([1.0, 0.0, 0.0], PDDeviceRGB.INSTANCE)
    assert color.to_rgb_int() == 0xFF0000
    white = PDColor([1.0, 1.0, 1.0], PDDeviceRGB.INSTANCE)
    assert white.to_rgb_int() == 0xFFFFFF


# ---------- pattern colours ----------


def test_pattern_only_color_zero_components() -> None:
    # Upstream PDColor(COSName, colorSpace): empty components.
    name = COSName.get_pdf_name("MyPattern")
    pattern_cs = PDPattern()
    color = PDColor(name, pattern_cs)
    assert color.get_components() == []
    assert color.get_pattern_name() is name
    assert color.is_pattern()


def test_pattern_with_tint_components() -> None:
    name = COSName.get_pdf_name("P1")
    pattern_cs = PDPattern(PDDeviceRGB.INSTANCE)
    color = PDColor([0.2, 0.4, 0.6], name, pattern_cs)
    assert color.get_pattern_name() is name
    assert color.get_components() == [0.2, 0.4, 0.6]
    assert color.is_pattern()


def test_get_pattern_name_none_for_non_pattern() -> None:
    color = PDColor([0.5, 0.25, 0.75], PDDeviceRGB.INSTANCE)
    assert color.get_pattern_name() is None


# ---------- to_cos_array round-trip ----------


@pytest.mark.parametrize(
    "components",
    [[], [0.5], [0.5, 0.25], [0.5, 0.25, 0.75], [0.1, 0.2, 0.3, 0.4]],
    ids=["empty", "one", "two", "three", "four"],
)
def test_to_cos_array_components_only(components: list[float]) -> None:
    color = PDColor(components, PDDeviceRGB.INSTANCE)
    array = color.to_cos_array()
    assert array.size() == len(components)
    for i, value in enumerate(components):
        assert array.get_object(i).value == pytest.approx(value)


def test_to_cos_array_appends_pattern_name() -> None:
    # Upstream: setFloatArray(components) then add(patternName).
    name = COSName.get_pdf_name("P1")
    pattern_cs = PDPattern(PDDeviceRGB.INSTANCE)
    color = PDColor([0.2, 0.4, 0.6], name, pattern_cs)
    array = color.to_cos_array()
    assert array.size() == 4
    assert array.get_object(0).value == pytest.approx(0.2)
    assert array.get_object(1).value == pytest.approx(0.4)
    assert array.get_object(2).value == pytest.approx(0.6)
    assert array.get_object(3) is name


def test_to_cos_array_pattern_only_just_name() -> None:
    name = COSName.get_pdf_name("OnlyPattern")
    pattern_cs = PDPattern()
    color = PDColor(name, pattern_cs)
    array = color.to_cos_array()
    assert array.size() == 1
    assert array.get_object(0) is name


def test_to_cos_array_round_trip_components() -> None:
    color = PDColor([0.1, 0.2, 0.3], PDDeviceRGB.INSTANCE)
    array = color.to_cos_array()
    rebuilt = PDColor(array, PDDeviceRGB.INSTANCE)
    assert rebuilt.get_components() == pytest.approx([0.1, 0.2, 0.3])
    assert rebuilt.get_pattern_name() is None


def test_to_cos_array_round_trip_pattern() -> None:
    name = COSName.get_pdf_name("P1")
    pattern_cs = PDPattern(PDDeviceRGB.INSTANCE)
    color = PDColor([0.2, 0.4, 0.6], name, pattern_cs)
    array = color.to_cos_array()
    rebuilt = PDColor(array, pattern_cs)
    assert rebuilt.get_components() == pytest.approx([0.2, 0.4, 0.6])
    assert rebuilt.get_pattern_name() == name


def test_parse_cos_array_with_integer_entries() -> None:
    array = COSArray()
    array.add(COSInteger.get(0))
    array.add(COSFloat(0.5))
    array.add(COSInteger.get(1))
    color = PDColor(array, PDDeviceRGB.INSTANCE)
    assert color.get_components() == pytest.approx([0.0, 0.5, 1.0])


# ---------- equality / hashing ----------


def test_equal_same_components_space_no_pattern() -> None:
    a = PDColor([0.5, 0.25, 0.75], PDDeviceRGB.INSTANCE)
    b = PDColor([0.5, 0.25, 0.75], PDDeviceRGB.INSTANCE)
    assert a == b
    assert hash(a) == hash(b)


def test_not_equal_different_components() -> None:
    a = PDColor([0.5, 0.25, 0.75], PDDeviceRGB.INSTANCE)
    b = PDColor([0.5, 0.25, 0.50], PDDeviceRGB.INSTANCE)
    assert a != b


def test_not_equal_different_color_space() -> None:
    a = PDColor([0.5], PDDeviceGray.INSTANCE)
    b = PDColor([0.5, 0.5, 0.5], PDDeviceRGB.INSTANCE)
    assert a != b


def test_equal_with_same_pattern_name() -> None:
    name = COSName.get_pdf_name("P1")
    pattern_cs = PDPattern(PDDeviceRGB.INSTANCE)
    a = PDColor([0.2, 0.4, 0.6], name, pattern_cs)
    b = PDColor([0.2, 0.4, 0.6], name, pattern_cs)
    assert a == b
    assert hash(a) == hash(b)


def test_not_equal_different_pattern_name() -> None:
    pattern_cs = PDPattern(PDDeviceRGB.INSTANCE)
    a = PDColor([0.2, 0.4, 0.6], COSName.get_pdf_name("P1"), pattern_cs)
    b = PDColor([0.2, 0.4, 0.6], COSName.get_pdf_name("P2"), pattern_cs)
    assert a != b


def test_not_equal_pattern_vs_no_pattern() -> None:
    name = COSName.get_pdf_name("P1")
    pattern_cs = PDPattern(PDDeviceRGB.INSTANCE)
    a = PDColor([0.2, 0.4, 0.6], name, pattern_cs)
    b = PDColor([0.2, 0.4, 0.6], PDDeviceRGB.INSTANCE)
    assert a != b


def test_not_equal_to_non_pdcolor() -> None:
    a = PDColor([0.5], PDDeviceGray.INSTANCE)
    assert a != "not a color"
    assert a != [0.5]
    assert (a == 42) is False


# ---------- to_string ----------


def test_to_string_shape() -> None:
    color = PDColor([1.0, 0.0, 0.5], PDDeviceRGB.INSTANCE)
    text = color.to_string()
    assert text.startswith("PDColor{components=[1.0, 0.0, 0.5]")
    assert "patternName=None" in text
    assert str(color) == text
