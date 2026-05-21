"""Wave 1365 parity tests for :class:`TextDialog`.

Upstream ``TextDialog.java`` is the modal text-display dialog used for the
"Extract Text" debugger feature. Existing waves cover the singleton
lifecycle, font-size handling and the headless build path. This file fills
in remaining upstream-mirrored semantics:

* ``clear()`` before ``show`` only resets the pending buffer (the toplevel
  is still unbuilt).
* ``set_text`` after ``clear`` correctly populates a fresh widget on show.
* Two ``init(owner)`` calls replace, not stack, the singleton (covers the
  "idempotent init" parity assertion beyond identity-replacement).
* The toplevel title matches the upstream "Text" string after first show.
* ``show()`` is idempotent — calling it twice returns the same toplevel.
* ``set_text`` on a long string preserves the full content end-to-end
  (no truncation in the Text-widget round trip).
* ``get_content_pane`` returns ``None`` until the dialog is built.
"""

from __future__ import annotations

import tkinter as tk

from pypdfbox.debugger.ui import TextDialog


def test_clear_before_show_only_resets_buffer(tk_root: tk.Tk) -> None:
    dialog = TextDialog(tk_root)
    dialog.set_text("buffered")
    dialog.clear()
    assert dialog._pending_text == ""
    # No toplevel was built by clear/set_text-without-show.
    assert dialog._toplevel is None


def test_set_text_after_clear_populates_widget(tk_root: tk.Tk) -> None:
    dialog = TextDialog(tk_root)
    dialog.set_text("first")
    dialog.clear()
    dialog.set_text("second")
    dialog.show()
    assert dialog._text is not None
    assert dialog._text.get("1.0", "end").rstrip("\n") == "second"


def test_two_inits_replace_singleton(tk_root: tk.Tk) -> None:
    """``init`` is idempotent and the latest call wins — assert by identity."""
    TextDialog.init(tk_root)
    first = TextDialog.instance()
    TextDialog.init(tk_root)
    second = TextDialog.instance()
    assert first is not None
    assert second is not None
    assert first is not second


def test_show_sets_upstream_title(tk_root: tk.Tk) -> None:
    """Upstream Java sets ``setTitle("Text")``; verify after first build."""
    dialog = TextDialog(tk_root)
    toplevel = dialog.show()
    assert toplevel.title() == "Text"


def test_show_is_idempotent(tk_root: tk.Tk) -> None:
    """A second ``show()`` call must return the same toplevel."""
    dialog = TextDialog(tk_root)
    first = dialog.show()
    second = dialog.show()
    assert first is second


def test_set_text_preserves_long_content(tk_root: tk.Tk) -> None:
    body = ("line " * 1000).rstrip()  # ~5 KB of text, no trailing space
    dialog = TextDialog(tk_root)
    dialog.set_text(body)
    dialog.show()
    assert dialog._text is not None
    # ``tk.Text`` always appends a trailing newline on read; strip it.
    assert dialog._text.get("1.0", "end").rstrip("\n") == body


def test_get_content_pane_returns_none_before_show() -> None:
    """Before ``show``, no toplevel exists (matches the deferred-build design)."""
    dialog = TextDialog(None)
    assert dialog.get_content_pane() is None
