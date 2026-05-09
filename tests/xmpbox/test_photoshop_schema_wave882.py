from __future__ import annotations

from collections.abc import Callable

import pytest

from tests.xmpbox.upstream import test_photoshop_schema as upstream_photoshop


@pytest.mark.parametrize(
    "placeholder",
    [
        upstream_photoshop.test_setting_value_in_array,
        upstream_photoshop.test_random_setting_value_in_array,
        upstream_photoshop.test_property_setter_in_array,
        upstream_photoshop.test_random_property_setter_in_array,
        upstream_photoshop.test_random_setter_simple,
    ],
)
def test_wave882_upstream_photoshop_placeholder_bodies(placeholder: Callable[[], None]) -> None:
    assert placeholder() is None
