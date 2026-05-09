from __future__ import annotations

from tests.pdmodel.graphics.test_graphics_tail_wave793 import _ArraylessColorSpace


def test_wave983_arrayless_color_space_helper_methods_are_exercised() -> None:
    color_space = _ArraylessColorSpace()

    assert color_space.get_number_of_components() == 1
    assert color_space.get_initial_color() is not color_space.get_initial_color()
