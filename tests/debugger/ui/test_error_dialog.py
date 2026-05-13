"""Hand-written tests for ``pypdfbox.debugger.ui.ErrorDialog``."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

from pypdfbox.debugger.ui import ErrorDialog
from pypdfbox.debugger.ui import error_dialog as module


@pytest.fixture(autouse=True)
def _reset_show_error_impl() -> Iterator[None]:
    module.set_show_error_impl(None)
    yield
    module.set_show_error_impl(None)


def test_constructor_accepts_one_arg() -> None:
    err = RuntimeError("boom")
    dialog = ErrorDialog(err)
    assert dialog._error is err
    assert dialog.is_filtering() is True


def test_constructor_accepts_two_args() -> None:
    err = ValueError("nope")
    dialog = ErrorDialog(None, err)
    assert dialog._error is err


def test_constructor_accepts_three_args() -> None:
    err = OSError("io")
    dialog = ErrorDialog(None, None, err)
    assert dialog._error is err


def test_constructor_rejects_non_exception() -> None:
    with pytest.raises(TypeError):
        ErrorDialog("not an exception")  # type: ignore[arg-type]


def test_constructor_rejects_too_many_args() -> None:
    with pytest.raises(TypeError):
        ErrorDialog(None, None, None, RuntimeError("x"))


def test_show_routes_through_show_error_impl() -> None:
    seen: list[tuple[str, str]] = []
    module.set_show_error_impl(lambda title, message: seen.append((title, message)))
    err = ValueError("kaboom")
    dialog = ErrorDialog(err)
    dialog.show()
    assert len(seen) == 1
    title, body = seen[0]
    assert title == "ValueError"
    assert "kaboom" in body


def test_set_visible_true_invokes_show() -> None:
    seen: list[Any] = []
    module.set_show_error_impl(lambda title, msg: seen.append((title, msg)))
    ErrorDialog(RuntimeError("hi")).set_visible(True)
    assert len(seen) == 1


def test_set_visible_false_is_noop() -> None:
    seen: list[Any] = []
    module.set_show_error_impl(lambda title, msg: seen.append((title, msg)))
    ErrorDialog(RuntimeError("hi")).set_visible(False)
    assert seen == []


def test_details_includes_stack_trace_when_enabled() -> None:
    try:
        raise RuntimeError("trace me")
    except RuntimeError as exc:
        dialog = ErrorDialog(exc)
    dialog.set_show_details(True)
    seen: list[tuple[str, str]] = []
    module.set_show_error_impl(lambda title, msg: seen.append((title, msg)))
    dialog.show()
    body = seen[0][1]
    assert "trace me" in body
    assert "test_details_includes_stack_trace_when_enabled" in body


def test_filtering_flag_is_respected() -> None:
    dialog = ErrorDialog(RuntimeError("x"))
    assert dialog.is_filtering() is True
    dialog.set_filtering(False)
    assert dialog.is_filtering() is False


def test_generate_stack_trace_handles_cause() -> None:
    try:
        try:
            raise ValueError("inner")
        except ValueError as inner:
            raise RuntimeError("outer") from inner
    except RuntimeError as outer:
        dialog = ErrorDialog(outer)
        trace = dialog.generate_stack_trace(outer)
    assert "RuntimeError: outer" in trace
    assert "Caused by: ValueError: inner" in trace


def test_filters_constant_matches_upstream() -> None:
    assert module._FILTERS == (
        "java.awt.",
        "javax.swing.",
        "sun.reflect.",
        "java.util.concurrent.",
    )
