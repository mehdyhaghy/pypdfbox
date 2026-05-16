"""Tests for the newly-promoted public surface of :class:`KToolTip`."""

from __future__ import annotations

import pytest

from pypdfbox.debugger.streampane.tooltip import KToolTip


def test_create_mark_up_populates_swatch() -> None:
    tip = KToolTip("0 0 0 1 k")
    payload = tip.get_tool_tip_text()
    assert payload is not None
    assert payload.segments[0].color_hex == "000000"


def test_create_mark_up_ignores_short_operand_list() -> None:
    tip = KToolTip("0 0 k")
    # Re-call directly: a short operand list should not overwrite the
    # tooltip state (still None because __init__ also short-circuited).
    tip.create_mark_up("1 0 0 k")
    assert tip.get_tool_tip_text() is None


def test_create_markup_alias_matches_public_method() -> None:
    # The pre-rename private spelling is still callable as an alias.
    assert KToolTip._create_markup is KToolTip.create_mark_up


def test_get_icc_color_space_raises_when_profile_missing() -> None:
    tip = KToolTip("0 0 0 0 k")
    # PDDeviceCMYK.get_icc_profile() returns None by default in pypdfbox,
    # so the upstream IOException contract is surfaced as OSError.
    with pytest.raises(OSError, match="CMYK color profile"):
        tip.get_icc_color_space()


def test_get_icc_profile_delegates_to_pd_device_cmyk() -> None:
    tip = KToolTip("0 0 0 0 k")
    # Mirrors PDDeviceCMYK.get_icc_profile() — None until installed.
    assert tip.get_icc_profile() is None
