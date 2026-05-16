"""Tests for the ported :py:meth:`ErrorDialog.to_string` method.

Mirrors upstream ``ErrorDialog.toString(StackTraceElement[])`` — renders a
list of stack frames as one indented string, optionally filtering out
boilerplate frames.
"""

from __future__ import annotations

import traceback

from pypdfbox.debugger.ui.error_dialog import ErrorDialog


def _capture_exception() -> Exception:
    try:
        raise RuntimeError("boom")
    except RuntimeError as exc:
        return exc


def test_to_string_renders_each_frame_with_indent() -> None:
    exc = _capture_exception()
    dialog = ErrorDialog(exc)
    rendered = dialog.to_string()
    # Each rendered frame uses upstream's "    "/"\r\n" indent + EOL.
    assert "    " in rendered
    assert "\r\n" in rendered
    # The capture helper's filename should appear at least once.
    assert __file__ in rendered or "test_error_dialog_to_string" in rendered


def test_to_string_filters_when_filtering_enabled() -> None:
    """When ``is_filtering`` is on, frames matching ``_FILTERS`` are dropped."""
    exc = _capture_exception()
    dialog = ErrorDialog(exc, is_filtering=True)
    # Synthesize a fake frame whose filename starts with one of the
    # noise prefixes; it should be excluded by ``to_string`` but kept
    # when filtering is disabled.
    fake_frame = traceback.FrameSummary("java.awt.EventQueue.java", 1, "dispatch")
    rendered_on = dialog.to_string([fake_frame])
    assert "java.awt" not in rendered_on
    dialog.set_filtering(False)
    rendered_off = dialog.to_string([fake_frame])
    assert "java.awt" in rendered_off


def test_to_string_default_uses_bound_exception_traceback() -> None:
    exc = _capture_exception()
    dialog = ErrorDialog(exc)
    # Default call (no argument) should render the bound exception's
    # own traceback frames.
    rendered = dialog.to_string()
    assert "in _capture_exception" in rendered
