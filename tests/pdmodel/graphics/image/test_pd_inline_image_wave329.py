from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel import PDResources
from pypdfbox.pdmodel.graphics.color import PDDeviceRGB
from pypdfbox.pdmodel.graphics.image import PDInlineImage


def _params_with_named_color_space(name: COSName) -> COSDictionary:
    params = COSDictionary()
    params.set_int("W", 1)
    params.set_int("H", 1)
    params.set_int("BPC", 8)
    params.set_item("CS", name)
    return params


def _resources_with_color_space(name: COSName, target: COSName) -> PDResources:
    resources = PDResources()
    resources.put(PDResources.COLOR_SPACE, name, target)
    return resources


def test_wave329_inline_image_resolves_named_color_space_from_resources() -> None:
    name = COSName.get_pdf_name("CS0")
    image = PDInlineImage(
        _params_with_named_color_space(name),
        b"\x00\x00\x00",
        _resources_with_color_space(name, COSName.get_pdf_name("DeviceRGB")),
    )

    assert image.get_color_space() is PDDeviceRGB.INSTANCE


def test_wave329_to_pil_image_uses_named_resource_color_space() -> None:
    name = COSName.get_pdf_name("CS0")
    image = PDInlineImage(
        _params_with_named_color_space(name),
        b"\x01\x02\x03",
        _resources_with_color_space(name, COSName.get_pdf_name("DeviceRGB")),
    )

    rendered = image.to_pil_image()

    assert rendered is not None
    assert rendered.mode == "RGB"
    assert rendered.getpixel((0, 0)) == (1, 2, 3)
