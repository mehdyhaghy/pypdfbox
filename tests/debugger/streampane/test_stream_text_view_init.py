"""Tests for the promoted :meth:`StreamTextView.init_ui` helper.

Upstream ``StreamTextView.initUI`` is a private helper invoked from the
constructor. We expose it as a public, callable method so the surface
mirrors the Java contract and so tests can rebuild the widget on the same
instance.
"""

from __future__ import annotations

import os

import pytest

from pypdfbox.debugger.streampane.stream_text_view import StreamTextView


def _tk_root_or_skip():
    if os.environ.get("PYPDFBOX_SKIP_TK", "") == "1":
        pytest.skip("PYPDFBOX_SKIP_TK=1 -- skipping Tk-bound test")
    import tkinter as tk

    try:
        root = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"no Tk display available: {exc}")
    root.withdraw()
    return root


def test_init_ui_is_called_from_constructor(tk_root) -> None:
    """Constructing the widget populates the underlying ``tk.Text``."""
    view = StreamTextView(tk_root, [("hello", None)], [])
    assert "hello" in view.text.get("1.0", "end-1c")


def test_init_ui_can_be_rerun_to_replace_content(tk_root) -> None:
    """Calling ``init_ui`` again rebuilds the widget with new segments.

    Upstream Swing reuses the same JPanel; our port spawns a fresh
    ``tk.Text`` on each call, but the parity guarantee is simply that the
    *visible* content matches the most recent ``init_ui`` invocation.
    """
    view = StreamTextView(tk_root, [("first", None)], [])
    view.init_ui([("second", None)], [])
    # After re-invocation, the latest text is visible.
    assert "second" in view.text.get("1.0", "end-1c")


def test_init_ui_registers_tags_before_inserting(tk_root) -> None:
    """Each ``(name, kwargs)`` entry in ``styles`` becomes a Tk tag."""
    styles = [("operator", {"foreground": "#19379c"})]
    view = StreamTextView(tk_root, [("BT", "operator")], styles)
    assert "operator" in view.text.tag_names()
