from __future__ import annotations

from types import CodeType, FunctionType

import pytest

from tests.pdmodel.documentinterchange.logicalstructure import (
    test_pd_structure_node_wave275,
)


def test_wave1144_fail_wrap_guard_helper_raises_when_called() -> None:
    source_test = (
        test_pd_structure_node_wave275.test_wave275_count_and_emptiness_do_not_materialize_wrappers
    )
    fail_wrap_code = next(
        const
        for const in source_test.__code__.co_consts
        if isinstance(const, CodeType) and const.co_name == "fail_wrap"
    )
    fail_wrap = FunctionType(fail_wrap_code, test_pd_structure_node_wave275.__dict__)

    with pytest.raises(AssertionError, match="wrap_kid should not be called"):
        fail_wrap(object())
