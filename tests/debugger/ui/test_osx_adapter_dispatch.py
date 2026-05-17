"""Tests for the reflection-dispatch helpers on ``OSXAdapter``.

These cover the Python equivalents of upstream ``OSXAdapter``'s
reflection-based helpers (``isMinJdk9`` / ``isCorrectMethod`` /
``invoke`` / ``callTarget`` / ``setApplicationEventHandled``).
"""

from __future__ import annotations

import sys
from typing import Any

import pytest

from pypdfbox.debugger.ui.osx_adapter import (
    call_target,
    invoke,
    is_correct_method,
    is_min_jdk9,
    set_application_event_handled,
)

# --- is_min_jdk9 -----------------------------------------------------------


def test_is_min_jdk9_returns_bool() -> None:
    # Don't assert a specific value -- result depends on the test machine.
    assert isinstance(is_min_jdk9(), bool)


def test_is_min_jdk9_true_on_darwin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "darwin")
    assert is_min_jdk9() is True


def test_is_min_jdk9_false_on_linux(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "linux")
    assert is_min_jdk9() is False


# --- is_correct_method -----------------------------------------------------


def test_is_correct_method_matches_name_and_signature() -> None:
    def func(a: int, b: str) -> None:
        del a, b

    assert is_correct_method(func, "func", (int, str)) is True


def test_is_correct_method_rejects_wrong_name() -> None:
    def func(a: int, b: str) -> None:
        del a, b

    assert is_correct_method(func, "other", (int, str)) is False


def test_is_correct_method_rejects_wrong_param_count() -> None:
    def func() -> None:
        return None

    assert is_correct_method(func, "func", (int, str)) is False


def test_is_correct_method_no_types_only_checks_name() -> None:
    def func(a: int) -> None:
        del a

    assert is_correct_method(func, "func") is True
    assert is_correct_method(func, "func", None) is True


def test_is_correct_method_handles_non_callable() -> None:
    assert is_correct_method(None, "anything") is False
    assert is_correct_method(42, "anything") is False


def test_is_correct_method_unannotated_params_count_only() -> None:
    def func(a, b):  # type: ignore[no-untyped-def]
        del a, b

    # No annotations, but count matches -- accept.
    assert is_correct_method(func, "func", (int, str)) is True


# --- invoke ----------------------------------------------------------------


class _Target:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    def real_method(self, value: Any) -> str:
        self.calls.append(("real_method", (value,)))
        return f"got:{value}"

    def on_event(self, event: Any) -> bool:
        self.calls.append(("on_event", (event,)))
        return True

    def takes_nothing(self) -> str:
        self.calls.append(("takes_nothing", ()))
        return "ok"


def test_invoke_missing_method_returns_none() -> None:
    target = _Target()
    assert invoke(target, "missing_method") is None
    assert target.calls == []


def test_invoke_real_method_returns_result() -> None:
    target = _Target()
    result = invoke(target, "real_method", "hello")
    assert result == "got:hello"
    assert target.calls == [("real_method", ("hello",))]


def test_invoke_signature_mismatch_returns_none() -> None:
    target = _Target()
    # ``takes_nothing`` accepts no args -- passing one should be caught.
    assert invoke(target, "takes_nothing", "extra") is None


def test_invoke_non_callable_attribute_returns_none() -> None:
    class Bag:
        not_callable = 42

    assert invoke(Bag(), "not_callable") is None


# --- call_target -----------------------------------------------------------


def test_call_target_dispatches_event() -> None:
    target = _Target()
    event = object()
    assert call_target(target, "on_event", event) is True
    assert target.calls == [("on_event", (event,))]


def test_call_target_without_event_uses_no_arg_path() -> None:
    target = _Target()
    assert call_target(target, "takes_nothing") == "ok"
    assert target.calls == [("takes_nothing", ())]


def test_call_target_missing_method_returns_none() -> None:
    target = _Target()
    assert call_target(target, "no_such", object()) is None


# --- set_application_event_handled -----------------------------------------


def test_set_application_event_handled_is_noop() -> None:
    # Documented no-op on Tk: Tk's createcommand dispatch already consumes
    # the event when our callback runs, so there is no flag to set.
    event = object()
    # Should accept any combination without raising.
    assert set_application_event_handled(event, True) is None
    assert set_application_event_handled(event, False) is None
    assert set_application_event_handled(None, True) is None
