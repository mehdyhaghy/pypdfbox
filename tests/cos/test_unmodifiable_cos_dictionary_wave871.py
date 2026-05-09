from __future__ import annotations

import pytest

from tests.cos.upstream import test_unmodifiable_cos_dictionary as upstream


@pytest.mark.parametrize(
    "test_name",
    [
        "test_unmodifiable_cos_dictionary",
        "test_set_item",
        "test_set_boolean",
        "test_set_name",
        "test_set_date",
        "test_set_embedded_date",
        "test_set_string",
        "test_set_embedded_string",
        "test_set_int",
        "test_set_embedded_int",
        "test_set_long",
        "test_set_float",
    ],
)
def test_unmodifiable_dictionary_placeholder_bodies_are_importable(
    test_name: str,
) -> None:
    assert getattr(upstream, test_name)() is None
