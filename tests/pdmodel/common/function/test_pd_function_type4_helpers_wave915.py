from __future__ import annotations

import pytest

from tests.pdmodel.common.function import test_pd_function_type4 as type4_mod


def test_wave915_make_type4_helper_populates_range_array() -> None:
    fn = type4_mod._make_type4(  # noqa: SLF001
        "{ dup mul }",
        domain=[-10.0, 10.0],
        rng=[0.0, 5.0],
    )

    assert fn.get_range_for_output(0) == (0.0, 5.0)
    assert fn.eval([3.0]) == pytest.approx([5.0])
