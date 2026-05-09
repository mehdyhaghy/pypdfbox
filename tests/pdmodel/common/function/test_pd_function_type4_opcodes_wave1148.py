from __future__ import annotations

import pytest

from tests.pdmodel.common.function.test_pd_function_type4_opcodes import _make


def test_make_helper_uses_default_domain() -> None:
    fn = _make("{ dup mul }")

    assert fn.eval([4.0]) == pytest.approx([16.0])

