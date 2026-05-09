from __future__ import annotations

import pytest

from pypdfbox.xmpbox.type import JobType
from tests.xmpbox.type.upstream.test_structured_type import (
    test_setter_then_getter as _test_setter_then_getter,
)


def test_setter_then_getter_skips_missing_typed_accessor_pair() -> None:
    with pytest.raises(pytest.skip.Exception):
        _test_setter_then_getter(JobType, "missingAccessor", "Text", [])
