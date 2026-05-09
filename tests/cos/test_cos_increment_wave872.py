from __future__ import annotations

import pytest

from tests.cos.upstream import test_cos_increment as upstream


@pytest.mark.parametrize(
    "test_name",
    [
        "test_incrementally_create_document",
        "test_concurrent_modification",
        "test_subsetting",
    ],
)
def test_increment_placeholder_bodies_are_importable(test_name: str) -> None:
    assert getattr(upstream, test_name)() is None
