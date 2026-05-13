"""Hand-written tests for ``pypdfbox.debugger.ui.TextDialog``."""

from __future__ import annotations

import tkinter as tk

import pytest

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


def test_set_text_font_height_applied_after_show(tk_root: tk.Tk) -> None:
    """Setting font height after the toplevel is built should re-apply the
    font to the underlying ``Text`` widget."""
    dialog = TextDialog(tk_root)
    dialog.show()
    dialog.set_text_font_height(22)
    spec = dialog._text.cget("font")
    assert "22" in str(spec)


def test_set_visible_true_shows_dialog(tk_root: tk.Tk) -> None:
    """``set_visible(True)`` defers to ``show`` and builds the toplevel."""
    dialog = TextDialog(tk_root)
    dialog.set_visible(True)
    assert dialog._toplevel is not None


def test_apply_font_noop_when_text_is_none() -> None:
    """The font helper short-circuits when the toplevel hasn't been built."""
    dialog = TextDialog(None)
    # Must not raise — ``_text`` is ``None`` until ``show`` runs.
    dialog._apply_font()


def test_extract_font_size_from_tuple() -> None:
    """The helper pulls element [1] from tuple specs (e.g. ``("Helvetica", 14)``)."""
    from pypdfbox.debugger.ui.text_dialog import _extract_font_size

    assert _extract_font_size(("Helvetica", 14)) == 14
    assert _extract_font_size(("Courier", 10, "bold")) == 10


def test_extract_font_size_from_string_spec() -> None:
    """The helper finds the first integer token in a string spec."""
    from pypdfbox.debugger.ui.text_dialog import _extract_font_size

    # The classic Tk font string is "Family Size Style".
    assert _extract_font_size("Helvetica 12 bold") == 12
    # Strings with no integer fall back to the default 10.
    assert _extract_font_size("just-letters") == 10
    # Non-tuple/non-string falls back to the default 10.
    assert _extract_font_size(None) == 10


def test_apply_font_falls_back_on_font_parse_error(
    tk_root: tk.Tk,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the font spec can't be parsed, ``_apply_font`` swallows the
    ``ValueError`` / ``tk.TclError`` and uses the default size."""
    from pypdfbox.debugger.ui import text_dialog as td

    dialog = TextDialog(tk_root)
    dialog.show()
    text = dialog._text
    assert text is not None

    # Make ``_extract_font_size`` raise to exercise the fallback path.
    def boom(_spec: object) -> int:
        raise ValueError("cannot parse")

    monkeypatch.setattr(td, "_extract_font_size", boom)
    dialog._apply_font()
    # Default 10 * 1.5 = 15.
    assert "15" in str(text.cget("font"))
