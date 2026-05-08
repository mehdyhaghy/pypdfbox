from __future__ import annotations

from pypdfbox.cos import COSName
from pypdfbox.pdmodel import PDResources
from pypdfbox.pdmodel.graphics.color import PDDeviceRGB


def test_get_color_space_resolves_named_alias_through_resources() -> None:
    res = PDResources()
    alias = COSName.get_pdf_name("CSAlias")
    target = COSName.get_pdf_name("CSDevice")
    res.put(PDResources.COLOR_SPACE, alias, target)
    res.put(PDResources.COLOR_SPACE, target, COSName.get_pdf_name("DeviceRGB"))

    assert res.get_color_space(alias) is PDDeviceRGB.INSTANCE


def test_get_color_space_self_alias_returns_none() -> None:
    res = PDResources()
    name = COSName.get_pdf_name("CS0")
    res.put(PDResources.COLOR_SPACE, name, name)

    assert res.get_color_space(name) is None


def test_get_color_space_alias_cycle_returns_none() -> None:
    res = PDResources()
    first = COSName.get_pdf_name("CS0")
    second = COSName.get_pdf_name("CS1")
    res.put(PDResources.COLOR_SPACE, first, second)
    res.put(PDResources.COLOR_SPACE, second, first)

    assert res.get_color_space(first) is None
