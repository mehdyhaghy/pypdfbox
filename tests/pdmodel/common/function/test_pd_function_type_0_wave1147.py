from __future__ import annotations

from tests.pdmodel.common.function.test_pd_function_type_0 import _build


def test_build_helper_sets_explicit_order() -> None:
    fn = _build(
        domain=[0.0, 1.0],
        range_=[0.0, 1.0],
        size=[2],
        bits=8,
        samples=[0, 255],
        order=3,
    )

    assert fn.get_order() == 3

