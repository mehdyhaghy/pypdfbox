"""Wave 1341 coverage-boost tests for ``pypdfbox.pdmodel.graphics.shading.pd_shading``.

Targets the still-uncovered branches in the wave-1332 snapshot:

* :meth:`PDShading.set_color_space_object` typed-color-space branch
  where ``get_cos_object()`` returns ``None`` (lines 235-236) — clears
  the ``/ColorSpace`` entry.
* :meth:`PDShading.get_function` single-dictionary /Function branch
  (line 368): wraps a non-array /Function via :meth:`PDFunction.create`.
* :meth:`PDShading.to_paint` base-class dispatch arms for shading types
  1-7 (lines 501-520). The concrete subclasses all override ``to_paint``
  so we exercise the base directly via ``PDShading.to_paint(instance)``.
"""

from __future__ import annotations

from typing import Any

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSStream
from pypdfbox.pdmodel.graphics.color.pd_color_space import PDColorSpace
from pypdfbox.pdmodel.graphics.shading.pd_shading import PDShading
from pypdfbox.pdmodel.graphics.shading.pd_shading_type1 import PDShadingType1
from pypdfbox.pdmodel.graphics.shading.pd_shading_type2 import PDShadingType2
from pypdfbox.pdmodel.graphics.shading.pd_shading_type3 import PDShadingType3
from pypdfbox.pdmodel.graphics.shading.pd_shading_type4 import PDShadingType4
from pypdfbox.pdmodel.graphics.shading.pd_shading_type5 import PDShadingType5
from pypdfbox.pdmodel.graphics.shading.pd_shading_type6 import PDShadingType6
from pypdfbox.pdmodel.graphics.shading.pd_shading_type7 import PDShadingType7

# ---------- set_color_space_object: PDColorSpace with None cos object -----


class _NoCosColorSpace(PDColorSpace):
    """Stub whose :meth:`get_cos_object` returns ``None`` — drives the
    ``set_color_space_object`` carve-out that clears ``/ColorSpace`` when
    the supplied typed color space has no backing COS object.
    """

    def get_cos_object(self) -> Any:  # noqa: ANN401
        return None

    def get_name(self) -> str:
        return "NoCos"

    def get_number_of_components(self) -> int:
        return 1

    def get_initial_color(self) -> Any:  # noqa: ANN401
        from pypdfbox.pdmodel.graphics.color.pd_color import PDColor

        return PDColor([0.0], self)


def test_set_color_space_object_clears_when_typed_cos_is_none() -> None:
    """A typed color space whose ``get_cos_object()`` returns ``None``
    clears the ``/ColorSpace`` entry rather than storing ``None``.
    """
    shading = PDShadingType1()
    # Seed an existing /ColorSpace so we can observe the clear.
    shading.set_color_space_object(
        # First use a valid wrapper to set the entry.
        _ValidCosColorSpace()
    )
    assert shading.get_cos_object().contains_key("ColorSpace")
    shading.set_color_space_object(_NoCosColorSpace())
    assert not shading.get_cos_object().contains_key("ColorSpace")


class _ValidCosColorSpace(PDColorSpace):
    """Helper whose ``get_cos_object()`` returns a non-None COSBase."""

    def get_cos_object(self) -> Any:  # noqa: ANN401
        from pypdfbox.cos import COSName

        return COSName.get_pdf_name("DeviceGray")

    def get_name(self) -> str:
        return "DeviceGray"

    def get_number_of_components(self) -> int:
        return 1

    def get_initial_color(self) -> Any:  # noqa: ANN401
        from pypdfbox.pdmodel.graphics.color.pd_color import PDColor

        return PDColor([0.0], self)


# ---------- get_function: single-dict (non-array) /Function ---------------


def test_get_function_returns_typed_pdfunction_for_dict_value() -> None:
    """A single dictionary /Function (not an array) flows through
    :meth:`PDFunction.create` and returns a typed wrapper.
    """
    # Build a minimal /FunctionType 2 (exponential interpolation) dict —
    # the simplest function type that PDFunction.create can dispatch on.
    func = COSDictionary()
    func.set_int("FunctionType", 2)
    domain = COSArray()
    domain.add(COSFloat(0.0))
    domain.add(COSFloat(1.0))
    func.set_item("Domain", domain)
    c0 = COSArray()
    c0.add(COSFloat(0.0))
    func.set_item("C0", c0)
    c1 = COSArray()
    c1.add(COSFloat(1.0))
    func.set_item("C1", c1)
    func.set_float("N", 1.0)

    shading = PDShadingType2()
    shading.get_cos_object().set_item("Function", func)
    # Subclasses override ``get_function`` with typed wrappers; we call
    # the base implementation directly to drive the
    # ``return PDFunction.create(item)`` arm (line 368).
    out = PDShading.get_function(shading)
    # Result is a typed PDFunction subclass, not a raw COSArray or None.
    assert out is not None
    assert not isinstance(out, COSArray)


# ---------- to_paint: base-class dispatch arms ---------------------------


def test_base_to_paint_dispatches_type1() -> None:
    """``PDShading.to_paint`` (base class) returns a Type1ShadingPaint when
    ``/ShadingType == 1``. Subclasses override ``to_paint``; we call the
    base implementation directly to exercise the dispatch arms.
    """
    from pypdfbox.pdmodel.graphics.shading.type1_shading_paint import Type1ShadingPaint

    shading = PDShadingType1()
    paint = PDShading.to_paint(shading)
    assert isinstance(paint, Type1ShadingPaint)


def test_base_to_paint_dispatches_type2() -> None:
    from pypdfbox.pdmodel.graphics.shading.axial_shading_paint import AxialShadingPaint

    shading = PDShadingType2()
    paint = PDShading.to_paint(shading)
    assert isinstance(paint, AxialShadingPaint)


def test_base_to_paint_dispatches_type3() -> None:
    from pypdfbox.pdmodel.graphics.shading.radial_shading_paint import (
        RadialShadingPaint,
    )

    shading = PDShadingType3()
    paint = PDShading.to_paint(shading)
    assert isinstance(paint, RadialShadingPaint)


def _stream_with_shading_type(shading_type: int) -> COSStream:
    stream = COSStream()
    stream.set_int("ShadingType", shading_type)
    return stream


def test_base_to_paint_dispatches_type4() -> None:
    from pypdfbox.pdmodel.graphics.shading.type4_shading_paint import Type4ShadingPaint

    shading = PDShadingType4(_stream_with_shading_type(4))
    paint = PDShading.to_paint(shading)
    assert isinstance(paint, Type4ShadingPaint)


def test_base_to_paint_dispatches_type5() -> None:
    from pypdfbox.pdmodel.graphics.shading.type5_shading_paint import Type5ShadingPaint

    shading = PDShadingType5(_stream_with_shading_type(5))
    paint = PDShading.to_paint(shading)
    assert isinstance(paint, Type5ShadingPaint)


def test_base_to_paint_dispatches_type6() -> None:
    from pypdfbox.pdmodel.graphics.shading.type6_shading_paint import Type6ShadingPaint

    shading = PDShadingType6(_stream_with_shading_type(6))
    paint = PDShading.to_paint(shading)
    assert isinstance(paint, Type6ShadingPaint)


def test_base_to_paint_dispatches_type7() -> None:
    from pypdfbox.pdmodel.graphics.shading.type7_shading_paint import Type7ShadingPaint

    shading = PDShadingType7(_stream_with_shading_type(7))
    paint = PDShading.to_paint(shading)
    assert isinstance(paint, Type7ShadingPaint)


def test_base_to_paint_unknown_type_returns_none() -> None:
    """When ``/ShadingType`` is not 1-7 the base ``to_paint`` returns
    ``None`` (matches the fallthrough at the end of the dispatch chain).
    """
    raw = PDShading()
    raw.get_cos_object().set_int("ShadingType", 99)
    assert PDShading.to_paint(raw) is None
