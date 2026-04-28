"""Hand-written tests for :class:`PDSeparation` covering the four
required accessors per CLAUDE.md task scope:
``get_name`` / ``get_alternate_color_space`` / ``get_tint_transform`` /
``to_rgb(tint)``.

Companion to ``test_pd_separation_parity.py`` which is the deeper round-out
suite. This file is the focused contract test for the task's named API
surface — keeping a small, hand-readable spec grounded in PDF 32000-1
§8.6.6.4 close to the round-out work.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName
from pypdfbox.pdmodel.common.function import PDFunction
from pypdfbox.pdmodel.graphics.color.pd_color import PDColor
from pypdfbox.pdmodel.graphics.color.pd_device_cmyk import PDDeviceCMYK
from pypdfbox.pdmodel.graphics.color.pd_device_rgb import PDDeviceRGB
from pypdfbox.pdmodel.graphics.color.pd_separation import PDSeparation


# ---------- helpers ----------


def _type2(c0: list[float], c1: list[float], n: float = 1.0) -> COSDictionary:
    """Build a /FunctionType 2 (exponential) dict for tint transforms."""
    d = COSDictionary()
    d.set_int("FunctionType", 2)
    d.set_item("Domain", COSArray.of_cos_floats([0.0, 1.0]))
    d.set_item("C0", COSArray.of_cos_floats(c0))
    d.set_item("C1", COSArray.of_cos_floats(c1))
    d.set_item("N", COSFloat(n))
    return d


def _separation(
    tint: COSDictionary,
    colorant: str = "PANTONE 185 C",
    alternate: str = "DeviceCMYK",
) -> PDSeparation:
    arr = COSArray()
    arr.add(COSName.get_pdf_name("Separation"))
    arr.add(COSName.get_pdf_name(colorant))
    arr.add(COSName.get_pdf_name(alternate))
    arr.add(tint)
    return PDSeparation(arr)


# ---------- get_name ----------


def test_get_name_returns_separation() -> None:
    """``get_name`` is the COS array head — always ``"Separation"``."""
    assert PDSeparation().get_name() == "Separation"


def test_get_name_constant_matches_class_attribute() -> None:
    assert PDSeparation.NAME == "Separation"
    assert PDSeparation().get_name() == PDSeparation.NAME


def test_get_number_of_components_is_one() -> None:
    """Separation always has a single tint component (PDF 32000-1
    §8.6.6.4)."""
    assert PDSeparation().get_number_of_components() == 1


def test_get_default_decode_is_zero_one() -> None:
    """Single-component decode array spans the full ``[0, 1]`` tint
    range (matches upstream ``PDSeparation.getDefaultDecode``)."""
    cs = PDSeparation()
    assert cs.get_default_decode(8) == [0.0, 1.0]


# ---------- get_alternate_color_space ----------


def test_get_alternate_color_space_named_rgb() -> None:
    cs = _separation(_type2([0.0, 0.0, 0.0], [1.0, 0.0, 0.0]), alternate="DeviceRGB")
    alt = cs.get_alternate_color_space()
    assert alt is not None
    assert alt.get_name() == "DeviceRGB"


def test_get_alternate_color_space_named_cmyk() -> None:
    cs = _separation(
        _type2([0.0, 0.0, 0.0, 0.0], [0.0, 1.0, 1.0, 0.0]), alternate="DeviceCMYK"
    )
    alt = cs.get_alternate_color_space()
    assert alt is not None
    assert alt.get_name() == "DeviceCMYK"


def test_alternate_round_trip_via_setter() -> None:
    cs = PDSeparation()
    cs.set_alternate_color_space(PDDeviceRGB.INSTANCE)
    alt = cs.get_alternate_color_space()
    assert alt is not None
    assert alt.get_name() == "DeviceRGB"


# ---------- get_tint_transform ----------


def test_get_tint_transform_returns_pd_function() -> None:
    cs = _separation(_type2([0.0, 0.0, 0.0], [1.0, 0.0, 0.0]))
    fn = cs.get_tint_transform()
    assert isinstance(fn, PDFunction)
    assert fn.get_function_type() == 2


def test_get_tint_transform_eval_at_endpoints() -> None:
    """Type 2 function with N=1 is linear: y = C0 + t*(C1-C0)."""
    cs = _separation(_type2([0.1, 0.2, 0.3], [0.7, 0.8, 0.9]))
    fn = cs.get_tint_transform()
    assert fn is not None
    assert fn.eval([0.0]) == pytest.approx([0.1, 0.2, 0.3], abs=1e-6)
    assert fn.eval([1.0]) == pytest.approx([0.7, 0.8, 0.9], abs=1e-6)


def test_get_tint_transform_none_for_default_placeholder() -> None:
    """Default-ctor PDSeparation has placeholder COSName slots — typed
    accessor returns ``None`` rather than blowing up."""
    assert PDSeparation().get_tint_transform() is None


# ---------- to_rgb(tint) ----------


def test_to_rgb_at_full_tint_via_cmyk_red() -> None:
    """Separation 'SpotRed' over CMYK alternate. Tint=1 -> CMYK
    (0,1,1,0) -> RGB (1,0,0)."""
    cs = _separation(
        _type2([0.0, 0.0, 0.0, 0.0], [0.0, 1.0, 1.0, 0.0]),
        colorant="SpotRed",
        alternate="DeviceCMYK",
    )
    rgb = cs.to_rgb([1.0])
    assert rgb == pytest.approx((1.0, 0.0, 0.0), abs=1e-6)


def test_to_rgb_at_zero_tint_is_white() -> None:
    """Tint=0 -> CMYK (0,0,0,0) -> RGB (1,1,1) (substractive
    no-ink)."""
    cs = _separation(
        _type2([0.0, 0.0, 0.0, 0.0], [0.0, 1.0, 1.0, 0.0]),
        alternate="DeviceCMYK",
    )
    rgb = cs.to_rgb([0.0])
    assert rgb == pytest.approx((1.0, 1.0, 1.0), abs=1e-6)


def test_to_rgb_returns_none_when_alternate_missing() -> None:
    """Default ctor has placeholder name in alternate slot —
    PDColorSpace.create can't resolve it, so to_rgb returns ``None``."""
    cs = PDSeparation()
    cs.set_tint_transform(_type2([0.0], [1.0]))
    assert cs.to_rgb([1.0]) is None


def test_to_rgb_returns_none_when_tint_transform_missing() -> None:
    cs = PDSeparation()
    cs.set_alternate_color_space(PDDeviceRGB.INSTANCE)
    assert cs.to_rgb([1.0]) is None


def test_to_rgb_via_pd_color_to_rgb() -> None:
    """End-to-end: a PDColor wrapping a Separation should evaluate to
    the same RGB tuple as cs.to_rgb directly."""
    cs = _separation(
        _type2([0.0, 0.0, 0.0, 0.0], [0.0, 0.0, 0.0, 1.0]),
        colorant="Black",
        alternate="DeviceCMYK",
    )
    via_color = PDColor([1.0], cs).to_rgb()
    via_cs = cs.to_rgb([1.0])
    assert via_color == via_cs == (0.0, 0.0, 0.0)


def test_setter_round_trip_via_to_rgb() -> None:
    """Build a PDSeparation entirely through setters, then exercise the
    full to_rgb pipeline."""
    cs = PDSeparation()
    cs.set_colorant_name("Black")
    cs.set_alternate_color_space(PDDeviceCMYK.INSTANCE)
    cs.set_tint_transform(_type2([0.0, 0.0, 0.0, 0.0], [0.0, 0.0, 0.0, 1.0]))
    rgb = cs.to_rgb([1.0])
    assert rgb == (0.0, 0.0, 0.0)


# ---------- initial color ----------


def test_initial_color_is_full_tint() -> None:
    """Per upstream, PDSeparation.getInitialColor() is single-component
    [1.0] (full tint)."""
    initial = PDSeparation().get_initial_color()
    assert initial.get_components() == [1.0]
