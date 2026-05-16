"""Hand-written tests for the new ``ErrorDialog`` helper methods.

Covers the wave-1309 additions:

* :meth:`ErrorDialog.create_content`
* :meth:`ErrorDialog.create_detailed_message`
* :meth:`ErrorDialog.create_error_message`
* :meth:`ErrorDialog.is_suppressed` / :meth:`mark_suppressed`
* :meth:`ErrorDialog.position`

The existing dialog tests live in ``test_error_dialog.py``; this file is
deliberately scoped to the new surface so it can be run in isolation.
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


# --- create_detailed_message (string-rendering form) ----------------------


def test_detailed_text_contains_type_and_message() -> None:
    """``detailed_text`` should include the exception type name and message."""
    try:
        raise ValueError("x")
    except ValueError as exc:
        out = ErrorDialog.detailed_text(exc)
    assert "ValueError" in out
    assert "x" in out


def test_detailed_text_without_traceback() -> None:
    """Even without a traceback, type+message render."""
    out = ErrorDialog.detailed_text(ValueError("x"))
    assert "ValueError" in out
    assert "x" in out


# --- is_suppressed / mark_suppressed --------------------------------------


def test_is_suppressed_false_by_default() -> None:
    dialog = ErrorDialog(RuntimeError("fresh"))
    assert dialog.is_suppressed() is False


def test_is_suppressed_true_after_mark_for_same_type() -> None:
    dialog = ErrorDialog(ValueError("first"))
    dialog.mark_suppressed()
    # A *different* dialog instance built around the same type should now
    # see the suppression -- it's session-level, not per-dialog.
    assert ErrorDialog(ValueError("second")).is_suppressed() is True


def test_is_suppressed_false_for_other_type() -> None:
    ErrorDialog(ValueError("foo")).mark_suppressed()
    assert ErrorDialog(RuntimeError("bar")).is_suppressed() is False


def test_is_suppressed_accepts_explicit_throwable() -> None:
    ErrorDialog(KeyError("k")).mark_suppressed()
    dialog = ErrorDialog(RuntimeError("unrelated"))
    assert dialog.is_suppressed(KeyError("any")) is True
    assert dialog.is_suppressed(RuntimeError("any")) is False


# --- Tk-backed widgets ----------------------------------------------------


def _need_tk() -> tk.Tk | None:
    """Return a fresh Tk root or skip if no display is available."""
    if os.environ.get("PYPDFBOX_SKIP_TK", "") == "1":
        pytest.skip("PYPDFBOX_SKIP_TK=1 -- skipping Tk-bound test")
    try:
        return tk.Tk()
    except tk.TclError:
        pytest.skip("no Tk display available")


def test_create_error_message_label_text() -> None:
    """The returned widget's ``text`` option round-trips the input."""
    root = _need_tk()
    assert root is not None
    try:
        root.withdraw()
        dialog = ErrorDialog(RuntimeError("ignored"))
        widget = dialog.create_error_message("oops", parent=root)
        assert widget is not None
        assert widget.cget("text") == "oops"
    finally:
        root.destroy()


def test_create_detailed_message_widget_contains_traceback() -> None:
    """The widget contents include the formatted traceback string."""
    root = _need_tk()
    assert root is not None
    try:
        root.withdraw()
        try:
            raise ValueError("boom")
        except ValueError as exc:
            dialog = ErrorDialog(exc)
            widget = dialog.create_detailed_message(exc, parent=root)
        assert widget is not None
        # ScrolledText exposes ``get`` like any Tk ``Text`` widget.
        body = widget.get("1.0", "end")
        assert "ValueError" in body
        assert "boom" in body
    finally:
        root.destroy()


def test_create_content_builds_container_with_children() -> None:
    """``create_content`` returns a Frame holding summary + detail widgets."""
    root = _need_tk()
    assert root is not None
    try:
        root.withdraw()
        try:
            raise RuntimeError("kaboom")
        except RuntimeError as exc:
            dialog = ErrorDialog(exc)
            container = dialog.create_content(parent=root)
        assert container is not None
        # Two children: the Label (summary) + the ScrolledText (detail).
        assert len(container.winfo_children()) >= 2
    finally:
        root.destroy()


def test_position_smoke() -> None:
    """``position`` should not raise on a real Tk toplevel."""
    root = _need_tk()
    assert root is not None
    try:
        root.withdraw()
        toplevel = tk.Toplevel(root)
        try:
            toplevel.withdraw()
            dialog = ErrorDialog(RuntimeError("x"))
            # parent=None -> screen-centring path.
            dialog.position(toplevel, parent=None)
            # parent supplied -> relative-centring path.
            dialog.position(toplevel, parent=root)
        finally:
            toplevel.destroy()
    finally:
        root.destroy()


def test_position_noop_when_no_component() -> None:
    """With no component and no bound toplevel, ``position`` is a silent no-op."""
    dialog = ErrorDialog(RuntimeError("x"))
    # Should not raise even though no Tk is involved.
    dialog.position(component=None, parent=None)
