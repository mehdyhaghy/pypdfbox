from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName
from pypdfbox.pdmodel import PDResources
from pypdfbox.pdmodel.graphics.color import PDDeviceRGB
from pypdfbox.pdmodel.graphics.pattern import PDTilingPattern
from pypdfbox.pdmodel.graphics.shading.pd_shading_type2 import PDShadingType2
from pypdfbox.pdmodel.graphics.state import PDExtendedGraphicsState

_COLOR_SPACE: COSName = COSName.get_pdf_name("ColorSpace")
_PATTERN: COSName = COSName.get_pdf_name("Pattern")
_SHADING: COSName = COSName.get_pdf_name("Shading")
_EXT_G_STATE: COSName = COSName.get_pdf_name("ExtGState")
_TYPE: COSName = COSName.TYPE  # type: ignore[attr-defined]
_PATTERN_TYPE: COSName = COSName.get_pdf_name("PatternType")
_SHADING_TYPE: COSName = COSName.get_pdf_name("ShadingType")


def test_get_color_space_dispatches_to_pd_device_rgb() -> None:
    res = PDResources()
    res.put(_COLOR_SPACE, COSName.get_pdf_name("CS0"), COSName.get_pdf_name("DeviceRGB"))
    cs = res.get_color_space(COSName.get_pdf_name("CS0"))
    assert cs is PDDeviceRGB.INSTANCE


def test_get_pattern_dispatches_to_tiling_pattern() -> None:
    res = PDResources()
    pattern_dict = COSDictionary()
    pattern_dict.set_item(_TYPE, COSName.get_pdf_name("Pattern"))
    pattern_dict.set_item(_PATTERN_TYPE, COSInteger(1))
    res.put(_PATTERN, COSName.get_pdf_name("P0"), pattern_dict)
    p = res.get_pattern(COSName.get_pdf_name("P0"))
    assert isinstance(p, PDTilingPattern)


def test_get_shading_dispatches_to_shading_type2() -> None:
    res = PDResources()
    shading_dict = COSDictionary()
    shading_dict.set_item(_SHADING_TYPE, COSInteger(2))
    # Minimal /ColorSpace entry — PDShading.create only inspects /ShadingType.
    shading_dict.set_item(
        COSName.get_pdf_name("ColorSpace"), COSName.get_pdf_name("DeviceRGB")
    )
    res.put(_SHADING, COSName.get_pdf_name("Sh0"), shading_dict)
    sh = res.get_shading(COSName.get_pdf_name("Sh0"))
    assert isinstance(sh, PDShadingType2)


def test_get_ext_gstate_returns_typed_wrapper() -> None:
    res = PDResources()
    egs_dict = COSDictionary()
    egs_dict.set_item(_TYPE, COSName.get_pdf_name("ExtGState"))
    res.put(_EXT_G_STATE, COSName.get_pdf_name("GS0"), egs_dict)
    egs = res.get_ext_gstate(COSName.get_pdf_name("GS0"))
    assert isinstance(egs, PDExtendedGraphicsState)
    assert egs.get_cos_object() is egs_dict


def test_get_color_space_missing_returns_none() -> None:
    res = PDResources()
    assert res.get_color_space(COSName.get_pdf_name("Nope")) is None


def test_get_pattern_missing_returns_none() -> None:
    res = PDResources()
    assert res.get_pattern(COSName.get_pdf_name("Nope")) is None


def test_get_shading_missing_returns_none() -> None:
    res = PDResources()
    assert res.get_shading(COSName.get_pdf_name("Nope")) is None


def test_get_ext_gstate_missing_returns_none() -> None:
    res = PDResources()
    assert res.get_ext_gstate(COSName.get_pdf_name("Nope")) is None


def test_get_property_list_missing_returns_none() -> None:
    res = PDResources()
    assert res.get_property_list(COSName.get_pdf_name("Nope")) is None


def test_get_color_space_array_form_for_indexed() -> None:
    # Array-form color space: [ /Indexed /DeviceRGB hival lookup ].
    res = PDResources()
    arr = COSArray(
        [
            COSName.get_pdf_name("Indexed"),
            COSName.get_pdf_name("DeviceRGB"),
            COSInteger(0),
            COSInteger(0),
        ]
    )
    res.put(_COLOR_SPACE, COSName.get_pdf_name("CS1"), arr)
    cs = res.get_color_space(COSName.get_pdf_name("CS1"))
    # Indexed dispatches via PDColorSpace.create — confirm class identity.
    from pypdfbox.pdmodel.graphics.color import PDIndexed

    assert isinstance(cs, PDIndexed)
