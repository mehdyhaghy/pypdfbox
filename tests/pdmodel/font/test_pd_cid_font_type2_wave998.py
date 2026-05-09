from __future__ import annotations

import pytest

from tests.pdmodel.font.test_pd_cid_font_type2_wave579 import (
    _fail_if_called,
    _ZeroUnitsTTF,
)


def test_wave998_negative_cache_parse_guard_helper_raises() -> None:
    with pytest.raises(AssertionError, match="cached None should not parse"):
        _fail_if_called(b"font-program")


def test_wave998_zero_units_helper_exposes_advance_widths() -> None:
    assert _ZeroUnitsTTF().advance_widths == [300, 600]
