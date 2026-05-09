"""Coverage for the skipped Type2CharString upstream sentinel body."""

from __future__ import annotations

from tests.fontbox.cff.upstream import test_type2_char_string as target


def test_no_upstream_tests_exist_sentinel_body() -> None:
    target.test_no_upstream_tests_exist()
