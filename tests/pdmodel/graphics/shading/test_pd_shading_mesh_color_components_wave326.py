from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName
from pypdfbox.pdmodel.graphics.shading import (
    PDShadingType4,
    PDShadingType5,
    PDShadingType6,
    PDShadingType7,
)

MeshShadingClass = (
    type[PDShadingType4]
    | type[PDShadingType5]
    | type[PDShadingType6]
    | type[PDShadingType7]
)

MESH_TYPES: list[MeshShadingClass] = [
    PDShadingType4,
    PDShadingType5,
    PDShadingType6,
    PDShadingType7,
]


def _function_type2_dict() -> COSDictionary:
    function = COSDictionary()
    function.set_int("FunctionType", 2)
    domain = COSArray()
    for value in (0.0, 1.0):
        domain.add(COSFloat(value))
    function.set_item("Domain", domain)
    c0 = COSArray()
    c0.add(COSFloat(0.0))
    function.set_item("C0", c0)
    c1 = COSArray()
    c1.add(COSFloat(1.0))
    function.set_item("C1", c1)
    function.set_int("N", 1)
    return function


def _device_n_color_space(component_names: tuple[str, ...]) -> COSArray:
    names = COSArray()
    for name in component_names:
        names.add(COSName.get_pdf_name(name))

    color_space = COSArray()
    color_space.add(COSName.get_pdf_name("DeviceN"))
    color_space.add(names)
    color_space.add(COSName.get_pdf_name("DeviceRGB"))
    color_space.add(_function_type2_dict())
    return color_space


@pytest.mark.parametrize("cls", MESH_TYPES)
def test_wave326_number_of_color_components_resolves_device_rgb_name(
    cls: MeshShadingClass,
) -> None:
    shading = cls()
    shading.set_color_space(COSName.get_pdf_name("DeviceRGB"))

    assert shading.get_number_of_color_components() == 3


@pytest.mark.parametrize("cls", MESH_TYPES)
def test_wave326_number_of_color_components_uses_cs_short_form(
    cls: MeshShadingClass,
) -> None:
    shading = cls()
    shading.get_cos_object().set_item(
        COSName.get_pdf_name("CS"), COSName.get_pdf_name("DeviceCMYK")
    )

    assert shading.get_number_of_color_components() == 4


@pytest.mark.parametrize("cls", MESH_TYPES)
def test_wave326_number_of_color_components_resolves_device_n_array(
    cls: MeshShadingClass,
) -> None:
    shading = cls()
    shading.set_color_space(_device_n_color_space(("Cyan", "Magenta", "Spot")))

    assert shading.get_number_of_color_components() == 3
