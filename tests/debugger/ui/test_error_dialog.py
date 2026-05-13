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


def test_is_showing_details_round_trips() -> None:
    dialog = ErrorDialog(RuntimeError("x"))
    assert dialog.is_showing_details() is False
    dialog.set_show_details(True)
    assert dialog.is_showing_details() is True
    dialog.set_show_details(False)
    assert dialog.is_showing_details() is False


def test_collect_skips_already_seen_throwable() -> None:
    """Cycles through ``__cause__`` should not loop forever — when the
    walker re-enters a throwable it has already rendered, ``_collect``
    short-circuits via ``id(throwable) in seen``."""
    err_a = RuntimeError("a")
    err_b = RuntimeError("b")
    # Build a two-step cycle: a → b → a.
    err_a.__cause__ = err_b
    err_b.__cause__ = err_a
    dialog = ErrorDialog(err_a)
    trace = dialog.generate_stack_trace(err_a)
    # Each error should appear exactly once, not infinitely.
    assert trace.count("RuntimeError: a") == 1
    assert trace.count("RuntimeError: b") == 1


def test_filtering_skips_suppressed_frames(monkeypatch: pytest.MonkeyPatch) -> None:
    """When filtering is on, frames whose ``filename`` matches a filter
    prefix are dropped from the rendered trace."""
    err = RuntimeError("filtered")
    dialog = ErrorDialog(err)
    dialog.set_filtering(True)

    # Build a synthetic FrameSummary list whose first entry matches a
    # filter prefix; ``_collect`` should skip it.
    import traceback as tb_mod

    fake_frames = [
        tb_mod.FrameSummary("java.awt.MyWidget", 1, "paint"),
        tb_mod.FrameSummary("user_code.py", 12, "do_thing"),
    ]
    monkeypatch.setattr(tb_mod, "extract_tb", lambda tb: fake_frames)
    # Give the exception a traceback so extract_tb is called.
    try:
        raise err  # noqa: TRY301
    except RuntimeError as e:
        out = dialog.generate_stack_trace(e)
    assert "java.awt.MyWidget" not in out
    assert "user_code.py:12 in do_thing" in out


def test_default_show_error_routes_through_messagebox(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``_default_show_error`` lazily imports ``tkinter.messagebox`` and
    forwards to ``showerror``."""
    captured: list[tuple[str, str]] = []

    # Build a tiny fake ``tkinter.messagebox`` module the lazy import
    # will find.
    import sys
    import types

    fake_messagebox = types.ModuleType("tkinter.messagebox")

    def fake_showerror(title: str, message: str) -> str:
        captured.append((title, message))
        return "ok"

    fake_messagebox.showerror = fake_showerror  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "tkinter.messagebox", fake_messagebox)

    result = module._default_show_error("MyTitle", "MyMessage")
    assert result == "ok"
    assert captured == [("MyTitle", "MyMessage")]
