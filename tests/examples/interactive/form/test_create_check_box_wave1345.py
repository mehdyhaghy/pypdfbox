"""Wave 1345 — coverage round-out for :class:`CreateCheckBox`.

Targets the remaining uncovered lines:

* the trivial ``__init__`` body (line 44);
* the :meth:`get_line_width` helper, both branches (border style
  present + ``None`` fallback) — lines 108-111.
"""

from __future__ import annotations

from typing import Any

from pypdfbox.examples.interactive.form.create_check_box import CreateCheckBox


class _FakeBorderStyle:
    def __init__(self, width: float) -> None:
        self._w = width

    def get_width(self) -> float:
        return self._w


class _FakeWidgetWithBorder:
    def __init__(self, width: float) -> None:
        self._bs = _FakeBorderStyle(width)

    def get_border_style(self) -> _FakeBorderStyle:
        return self._bs


class _FakeWidgetWithoutBorder:
    def get_border_style(self) -> Any:
        return None


def test_constructor_is_inert() -> None:
    """The ``__init__`` body is just ``pass`` — line 44."""
    assert CreateCheckBox() is not None


def test_get_line_width_uses_border_style_when_present() -> None:
    """The ``if bs is not None`` branch returns the border-style width."""
    widget = _FakeWidgetWithBorder(3.5)
    assert CreateCheckBox.get_line_width(widget) == 3.5


def test_get_line_width_defaults_to_one_when_border_absent() -> None:
    """When the widget has no border style, the helper falls back to
    ``1.0`` — line 111."""
    widget = _FakeWidgetWithoutBorder()
    assert CreateCheckBox.get_line_width(widget) == 1.0
