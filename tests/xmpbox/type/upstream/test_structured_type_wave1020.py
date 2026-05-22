from __future__ import annotations

import pytest

from pypdfbox.xmpbox.type import JobType
from tests.xmpbox.type.upstream.test_structured_type import (
    test_setter_then_getter as _test_setter_then_getter,
)


def test_setter_then_getter_flags_missing_typed_accessor_pair() -> None:
    """Wave 1020 originally asserted the helper *skipped* when the param row
    referenced an undeclared setter/getter pair; wave 1382 tightened the
    invariant — every row in ``_PARAMS`` must declare both methods — and
    the helper now raises ``AssertionError`` for missing pairs."""
    with pytest.raises(AssertionError, match="missing setter for"):
        _test_setter_then_getter(JobType, "missingAccessor", "Text", [])
