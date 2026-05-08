from __future__ import annotations

import pytest

from pypdfbox.pdmodel.graphics.shading import PDShadingType4, PDShadingType5


@pytest.mark.parametrize("cls", [PDShadingType4, PDShadingType5])
def test_wave311_negative_decode_parameter_is_out_of_range(
    cls: type[PDShadingType4] | type[PDShadingType5],
) -> None:
    shading = cls()
    shading.set_decode([0.0, 100.0, 50.0, 200.0])

    assert shading.get_decode_for_parameter(-1) is None
    assert shading.get_decode_for_parameter(0) == (0.0, 100.0)
