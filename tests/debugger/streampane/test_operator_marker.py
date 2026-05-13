"""Tests for :mod:`pypdfbox.debugger.streampane.operator_marker`."""

from __future__ import annotations

import pytest

from pypdfbox.contentstream.operator_name import OperatorName
from pypdfbox.debugger.streampane.operator_marker import OperatorMarker


def test_unknown_operator_returns_none() -> None:
    assert OperatorMarker.get_style("not-an-operator") is None


def test_text_object_operators_get_green_style() -> None:
    style = OperatorMarker.get_style(OperatorName.BEGIN_TEXT)
    assert style is not None
    assert style["foreground"] == "#006400"
    assert style["weight"] == "bold"
    # END_TEXT shares the same dict object as BEGIN_TEXT in upstream.
    assert OperatorMarker.get_style(OperatorName.END_TEXT) is style


def test_graphics_state_operators_share_red_style() -> None:
    save_style = OperatorMarker.get_style(OperatorName.SAVE)
    restore_style = OperatorMarker.get_style(OperatorName.RESTORE)
    assert save_style is not None
    assert save_style["foreground"] == "#ff4444"
    assert save_style is restore_style


def test_cm_operator_gets_cyan_style() -> None:
    style = OperatorMarker.get_style(OperatorName.CONCAT)
    assert style is not None
    assert style["foreground"] == "#01a9db"


def test_inline_image_operators_share_blue_style() -> None:
    begin = OperatorMarker.get_style(OperatorName.BEGIN_INLINE_IMAGE)
    end = OperatorMarker.get_style(OperatorName.END_INLINE_IMAGE)
    assert begin is end
    assert begin is not None
    assert begin["foreground"] == "#4775a3"


def test_image_data_operator_gets_orange_style() -> None:
    style = OperatorMarker.get_style(OperatorName.BEGIN_INLINE_IMAGE_DATA)
    assert style is not None
    assert style["foreground"] == "#ffa500"


def test_constructor_is_disabled() -> None:
    with pytest.raises(TypeError):
        OperatorMarker()
