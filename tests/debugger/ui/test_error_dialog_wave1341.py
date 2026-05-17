"""Wave 1341 coverage-boost tests for
``pypdfbox.debugger.ui.error_dialog``.

Targets the still-uncovered branches in the wave-1332 snapshot:

* :meth:`ErrorDialog.create_content` ``tk.TclError`` fallback when
  ``tk.Frame()`` cannot construct (lines 150-151).
* :meth:`ErrorDialog.create_error_message` ``BaseException`` -> string
  coercion (line 173) and ``tk.TclError`` widget-construction fallback
  (lines 180-181).
* :meth:`ErrorDialog.create_detailed_message` ``throwable`` defaulting
  to ``self._error`` when ``None`` is passed (line 200), and
  ``tk.TclError`` widget-construction fallback (lines 208-209).
* :meth:`ErrorDialog.position` ``tk.TclError`` exception arm
  (lines 291-292) — when the component's Tk operations raise.

All Tk-touching tests guard with the project's ``PYPDFBOX_SKIP_TK``
contract via the ``tk_root`` fixture; the no-Tk fallbacks are driven
through monkey-patching :mod:`tkinter` constructors to raise.
"""

from __future__ import annotations

import os
import tkinter as tk
from collections.abc import Iterator

import pytest

from pypdfbox.debugger.ui import ErrorDialog
from pypdfbox.debugger.ui import error_dialog as module


@pytest.fixture(autouse=True)
def _reset_suppression() -> Iterator[None]:
    module.clear_suppressed_types()
    yield
    module.clear_suppressed_types()


# ---------- create_content: TclError fallback -----------------------------


def test_create_content_returns_none_when_tk_frame_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If ``tk.Frame()`` raises ``TclError`` (e.g. headless or missing
    display) ``create_content`` returns ``None`` rather than propagating.
    """

    def _raise(*_args: object, **_kwargs: object) -> tk.Frame:
        raise tk.TclError("no display")

    monkeypatch.setattr(module.tk, "Frame", _raise)
    dialog = ErrorDialog(RuntimeError("x"))
    assert dialog.create_content() is None


# ---------- create_error_message: BaseException + TclError ---------------


def test_create_error_message_coerces_base_exception_to_string() -> None:
    """Passing a ``BaseException`` (not a pre-rendered string) uses
    ``str(exception)`` -- with a fallback to the exception's type name
    when the message is empty.
    """

    if os.environ.get("PYPDFBOX_SKIP_TK", "") == "1":
        pytest.skip("PYPDFBOX_SKIP_TK=1 -- skipping Tk-bound test")
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("no Tk display available")
    try:
        root.withdraw()
        dialog = ErrorDialog(RuntimeError("ignored"))
        # An exception with an empty message hits the
        # ``str(...) or type(...).__name__`` fallback.
        widget = dialog.create_error_message(ValueError(""), parent=root)
        assert widget is not None
        # Falls back to type-name when the message is empty.
        assert widget.cget("text") == "ValueError"
    finally:
        root.destroy()


def test_create_error_message_returns_none_when_label_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``tk.Label()`` raising ``TclError`` -> ``None`` (silent no-op)."""

    def _raise(*_args: object, **_kwargs: object) -> tk.Label:
        raise tk.TclError("no display")

    monkeypatch.setattr(module.tk, "Label", _raise)
    dialog = ErrorDialog(RuntimeError("x"))
    assert dialog.create_error_message("plain text") is None


# ---------- create_detailed_message: throwable default + TclError -------


def test_create_detailed_message_defaults_throwable_to_self_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When ``throwable`` is omitted/None, the dialog uses its bound
    exception. We monkeypatch the ScrolledText constructor to raise so
    we only need to verify the default-resolution path runs without
    consulting Tk; the return value is then the ``None`` carve-out.
    """

    def _raise(*_args: object, **_kwargs: object) -> object:
        raise tk.TclError("no display")

    monkeypatch.setattr(module.scrolledtext, "ScrolledText", _raise)
    dialog = ErrorDialog(RuntimeError("default-throwable"))
    # ``throwable=None`` -> defaults to self._error, then ScrolledText
    # raises -> we get ``None`` back. The default-throwable branch is
    # what we care about here (covers line 200).
    assert dialog.create_detailed_message(None) is None


def test_create_detailed_message_returns_none_when_scrolled_text_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``tk.scrolledtext.ScrolledText()`` raising -> ``None``."""

    def _raise(*_args: object, **_kwargs: object) -> object:
        raise tk.TclError("no display")

    monkeypatch.setattr(module.scrolledtext, "ScrolledText", _raise)
    dialog = ErrorDialog(RuntimeError("x"))
    assert dialog.create_detailed_message(RuntimeError("y")) is None


# ---------- position: outer TclError handler ------------------------------


class _FakeComponentRaises:
    """Stand-in for a Tk widget whose first inspected method raises."""

    def update_idletasks(self) -> None:
        raise tk.TclError("simulated")

    def winfo_reqwidth(self) -> int:
        return 100

    def winfo_reqheight(self) -> int:
        return 100

    def winfo_screenwidth(self) -> int:
        return 1024

    def winfo_screenheight(self) -> int:
        return 768

    def wm_geometry(self, _geom: str) -> None:
        return


def test_position_swallows_tcl_error_from_widget_calls() -> None:
    """The outer ``try / except tk.TclError`` returns silently when any
    widget-level call raises (covers lines 291-292).
    """
    dialog = ErrorDialog(RuntimeError("x"))
    # Returns None silently, no exception propagated.
    dialog.position(component=_FakeComponentRaises(), parent=None)


def test_position_silent_when_owner_inspection_raises() -> None:
    """The owner-relative path also gets the same TclError swallow."""
    dialog = ErrorDialog(RuntimeError("x"))

    class _FakeParent:
        def winfo_rootx(self) -> int:
            raise tk.TclError("owner gone")

        def winfo_rooty(self) -> int:
            return 0

        def winfo_width(self) -> int:
            return 100

        def winfo_height(self) -> int:
            return 100

    class _FakeComponentRaisesOnRootx:
        def update_idletasks(self) -> None:
            return

        def winfo_reqwidth(self) -> int:
            return 100

        def winfo_reqheight(self) -> int:
            return 100

        def wm_geometry(self, _geom: str) -> None:
            return

    dialog.position(
        component=_FakeComponentRaisesOnRootx(), parent=_FakeParent()
    )
