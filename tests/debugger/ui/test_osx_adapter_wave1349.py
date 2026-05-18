"""Wave 1349 coverage-boost tests for ``OSXAdapter``.

Targets the residual branches in :func:`is_correct_method` —
``inspect.signature`` failure path, string-annotation mismatch path,
and non-string annotation mismatch path.
"""

from __future__ import annotations

import inspect
from typing import Any

import pytest

from pypdfbox.debugger.ui.osx_adapter import is_correct_method


def test_is_correct_method_signature_unintrospectable_returns_false(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Lines 89-90 — ``inspect.signature`` raises ``ValueError``
    on builtins like ``len``; covered branch returns ``False``."""

    def fn(a: int) -> None:  # name + arity match the expected ``[int]``
        return None

    def boom(_method: Any) -> inspect.Signature:
        raise ValueError("no signature")

    monkeypatch.setattr(inspect, "signature", boom)
    assert is_correct_method(fn, "fn", [int]) is False


def test_is_correct_method_string_annotation_mismatch_returns_false() -> None:
    """Line 112 — string annotation (from ``from __future__ import
    annotations``) that doesn't match the expected type name."""
    # Because of ``from __future__ import annotations`` here, the
    # parameter annotation ``int`` is stored as the literal string
    # ``"int"``. Asking for ``str`` (which stringifies to ``"str"``) is
    # a name mismatch, hitting the string-comparison miss branch.

    def fn(a: int) -> None:
        return None

    assert is_correct_method(fn, "fn", [str]) is False


def test_is_correct_method_string_annotation_match_returns_true() -> None:
    """Companion to the mismatch case above — names match, expect True."""

    def fn(a: int) -> None:
        return None

    assert is_correct_method(fn, "fn", [int]) is True


def test_is_correct_method_non_string_annotation_mismatch_returns_false() -> None:
    """Lines 114-115 — annotation is a real class object (not a
    string) and is *not* the expected type."""

    # Build a function whose annotation is a live class object rather
    # than the deferred string form. ``__future__ annotations`` makes
    # source-declared annotations strings, so synthesise the function
    # via ``exec`` + ``__annotations__`` injection.
    def fn(a):  # noqa: ANN001
        return None

    fn.__annotations__ = {"a": int}  # live class object, not "int"

    assert is_correct_method(fn, "fn", [str]) is False
    # And the match case to prove the live-class path also takes the
    # success exit (loop body completes without returning False).
    assert is_correct_method(fn, "fn", [int]) is True
