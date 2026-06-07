"""Wave 1512 — coverage round-out for ``PDFRenderer`` shading colour helpers.

Pins the defensive fall-open arms of ``_shading_background_rgb`` and
``_convert_shading_output``: a shading object whose ``/Background``,
``/ColorSpace`` accessors raise, return ``None``, yield an empty array, or whose
typed colour space's ``to_rgb`` raises must degrade to ``None`` (or the Device
heuristic) — never propagate the exception. This mirrors upstream
``ShadingContext`` / ``AxialShadingContext`` which only convert colour they can
positively resolve and otherwise leave the pixel to the gradient/background
ladder.

Each test asserts the observable return value, not merely line execution.
"""

from __future__ import annotations

from typing import Any

from pypdfbox.cos import COSName
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.rendering import PDFRenderer


def _make_renderer() -> PDFRenderer:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    doc.add_page(PDPage(PDRectangle(0.0, 0.0, 40.0, 40.0)))
    renderer = PDFRenderer(doc)
    renderer.render_image(0)
    return renderer


class _FloatArray:
    """Stand-in for a ``COSArray`` exposing ``to_float_array``."""

    def __init__(self, values: list[float], *, raises: bool = False) -> None:
        self._values = values
        self._raises = raises

    def to_float_array(self) -> list[float]:
        if self._raises:
            raise ValueError("boom")
        return list(self._values)


class _Shading:
    """Minimal shading stub for the colour-helper code paths."""

    def __init__(
        self,
        *,
        background: Any = None,
        bg_raises: bool = False,
        color_space: Any = None,
        cs_raises: bool = False,
        cs_object: Any = None,
        cs_object_raises: bool = False,
    ) -> None:
        self._background = background
        self._bg_raises = bg_raises
        self._color_space = color_space
        self._cs_raises = cs_raises
        self._cs_object = cs_object
        self._cs_object_raises = cs_object_raises

    def get_background(self) -> Any:
        if self._bg_raises:
            raise ValueError("boom")
        return self._background

    def get_color_space(self) -> Any:
        if self._cs_raises:
            raise ValueError("boom")
        return self._color_space

    def get_color_space_object(self, resources: Any) -> Any:
        if self._cs_object_raises:
            raise ValueError("boom")
        return self._cs_object


class _ColorSpace:
    """Typed colour-space stub exposing ``to_rgb``."""

    def __init__(self, *, result: Any = None, raises: bool = False) -> None:
        self._result = result
        self._raises = raises

    def to_rgb(self, values: list[float]) -> Any:
        if self._raises:
            raise ValueError("boom")
        return self._result


# --------------------------------------------------------------------------
# _shading_background_rgb
# --------------------------------------------------------------------------


def test_shading_background_none_returns_none() -> None:
    r = _make_renderer()
    assert r._shading_background_rgb(_Shading(background=None)) is None


def test_shading_background_get_background_raises_returns_none() -> None:
    r = _make_renderer()
    assert r._shading_background_rgb(_Shading(bg_raises=True)) is None


def test_shading_background_to_float_array_raises_returns_none() -> None:
    r = _make_renderer()
    bg = _FloatArray([], raises=True)
    assert r._shading_background_rgb(_Shading(background=bg)) is None


def test_shading_background_empty_array_returns_none() -> None:
    r = _make_renderer()
    bg = _FloatArray([])
    assert r._shading_background_rgb(_Shading(background=bg)) is None


def test_shading_background_device_gray_uses_function_heuristic() -> None:
    r = _make_renderer()
    bg = _FloatArray([1.0])
    cs = COSName.get_pdf_name("DeviceGray")
    # DeviceGray g=1.0 -> white via _function_output_to_rgb.
    assert r._shading_background_rgb(_Shading(background=bg, color_space=cs)) == (
        255,
        255,
        255,
    )


def test_shading_background_get_color_space_raises_falls_to_heuristic() -> None:
    r = _make_renderer()
    bg = _FloatArray([0.0])
    # get_color_space raises -> cs_name None -> single-component gray heuristic.
    out = r._shading_background_rgb(_Shading(background=bg, cs_raises=True))
    assert out == (0, 0, 0)


def test_shading_background_non_device_cs_routes_through_to_rgb() -> None:
    r = _make_renderer()
    bg = _FloatArray([0.5])
    cs = COSName.get_pdf_name("Separation")
    sh = _Shading(
        background=bg,
        color_space=cs,
        cs_object=_ColorSpace(result=(1.0, 0.0, 0.0)),
    )
    assert r._shading_background_rgb(sh) == (255, 0, 0)


# --------------------------------------------------------------------------
# _convert_shading_output
# --------------------------------------------------------------------------


def test_convert_shading_output_cs_object_raises_returns_none() -> None:
    r = _make_renderer()
    assert r._convert_shading_output(_Shading(cs_object_raises=True), [0.5]) is None


def test_convert_shading_output_no_to_rgb_returns_none() -> None:
    r = _make_renderer()
    # cs_object is a plain object with no ``to_rgb`` attribute.
    assert r._convert_shading_output(_Shading(cs_object=object()), [0.5]) is None


def test_convert_shading_output_to_rgb_raises_returns_none() -> None:
    r = _make_renderer()
    sh = _Shading(cs_object=_ColorSpace(raises=True))
    assert r._convert_shading_output(sh, [0.5]) is None


def test_convert_shading_output_to_rgb_none_returns_none() -> None:
    r = _make_renderer()
    sh = _Shading(cs_object=_ColorSpace(result=None))
    assert r._convert_shading_output(sh, [0.5]) is None


def test_convert_shading_output_clamps_and_converts() -> None:
    r = _make_renderer()
    sh = _Shading(cs_object=_ColorSpace(result=(0.0, 1.0, 0.0)))
    # Out-of-range inputs are clamped to [0,1] before to_rgb; result passes back.
    assert r._convert_shading_output(sh, [2.0, -1.0]) == (0.0, 1.0, 0.0)
