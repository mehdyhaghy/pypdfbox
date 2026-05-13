"""Hand-written tests for ``pypdfbox.debugger.ui.TextDialog``."""

from __future__ import annotations

import tkinter as tk

from pypdfbox.debugger.ui import TextDialog


def test_init_and_instance_singleton(tk_root: tk.Tk) -> None:
    TextDialog.init(tk_root)
    inst = TextDialog.instance()
    assert isinstance(inst, TextDialog)
    # ``init`` is idempotent: replaces the singleton.
    TextDialog.init(tk_root)
    assert TextDialog.instance() is not None


def test_set_text_before_show_is_replayed_on_open(tk_root: tk.Tk) -> None:
    dialog = TextDialog(tk_root)
    dialog.set_text("hello world")
    toplevel = dialog.show()
    assert toplevel is not None
    text_widget = dialog._text
    assert text_widget is not None
    assert text_widget.get("1.0", "end").rstrip("\n") == "hello world"


def test_clear_resets_content(tk_root: tk.Tk) -> None:
    dialog = TextDialog(tk_root)
    dialog.set_text("something")
    dialog.show()
    dialog.clear()
    text_widget = dialog._text
    assert text_widget is not None
    assert text_widget.get("1.0", "end").strip() == ""


def test_set_visible_false_withdraws(tk_root: tk.Tk) -> None:
    dialog = TextDialog(tk_root)
    dialog.show()
    dialog.set_visible(False)
    toplevel = dialog.get_content_pane()
    assert toplevel is not None
    # ``state()`` reports ``withdrawn`` once hidden.
    assert toplevel.state() == "withdrawn"


def test_set_text_font_height_applies_before_show(tk_root: tk.Tk) -> None:
    dialog = TextDialog(tk_root)
    dialog.set_text_font_height(18)
    dialog.show()
    text_widget = dialog._text
    assert text_widget is not None
    font_spec = text_widget.cget("font")
    # The font may be returned as tuple, string, or named font. Just assert
    # the size we requested appears somewhere in the spec.
    assert "18" in str(font_spec)


def test_pack_does_not_raise(tk_root: tk.Tk) -> None:
    dialog = TextDialog(tk_root)
    # Should not raise when the toplevel hasn't been built yet.
    dialog.pack()
    dialog.show()
    dialog.pack()


def test_headless_construction_does_not_require_tk_root() -> None:
    # Constructing should not need a Tk display.
    dialog = TextDialog(None)
    dialog.set_text("buffered")
    assert dialog._pending_text == "buffered"
