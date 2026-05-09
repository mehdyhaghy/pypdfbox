from __future__ import annotations

import pytest

from tests.pdmodel.common.function import test_pd_function_type4_wave443 as wave443


def test_wave916_make_helper_populates_range_array() -> None:
    fn = wave443._make(  # noqa: SLF001
        "{ 2 mul }",
        domain=[0.0, 10.0],
        rng=[0.0, 6.0],
    )

    assert fn.get_range_for_output(0) == (0.0, 6.0)
    assert fn.eval([4.0]) == pytest.approx([6.0])
