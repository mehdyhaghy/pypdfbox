"""Hand-written tests for ``pypdfbox.debugger.ui.LogDialog``."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Iterator

import pytest

from pypdfbox.debugger.ui import DebugLog, LogDialog
from pypdfbox.debugger.ui import debug_log as debug_log_module


@pytest.fixture(autouse=True)
def _reset_dialog_sink() -> Iterator[None]:
    debug_log_module.set_dialog_sink(None)
    yield
    debug_log_module.set_dialog_sink(None)


def test_counters_increment_per_level() -> None:
    dialog = LogDialog(owner=None)
    dialog.log("pypdfbox.x", "info", "i1")
    dialog.log("pypdfbox.x", "warn", "w1")
    dialog.log("pypdfbox.x", "error", "e1")
    dialog.log("pypdfbox.x", "fatal", "f1")
    dialog.log("pypdfbox.x", "debug", "d1")
    dialog.log("pypdfbox.x", "trace", "t1")
    assert dialog.get_other_count() == 3  # info + debug + trace
    assert dialog.get_warn_count() == 1
    assert dialog.get_error_count() == 1
    assert dialog.get_fatal_count() == 1
    assert dialog.get_exception_count() == 0


def test_exception_count_increments_with_throwable() -> None:
    dialog = LogDialog(owner=None)
    dialog.log("pypdfbox.x", "error", "with exc", RuntimeError("boom"))
    assert dialog.get_exception_count() == 1


def test_unknown_level_raises() -> None:
    dialog = LogDialog(owner=None)
    with pytest.raises(ValueError):
        dialog.log("name", "panic", "msg")


def test_status_text_formats_singular_and_plural() -> None:
    dialog = LogDialog(owner=None)
    dialog.log("x", "error", "e")
    assert dialog.get_status_text() == "1 error"
    dialog.log("x", "error", "e2")
    assert "2 errors" in dialog.get_status_text()


def test_status_text_includes_all_buckets_with_exceptions() -> None:
    dialog = LogDialog(owner=None)
    dialog.log("x", "fatal", "f")
    dialog.log("x", "error", "e", RuntimeError("x"))
    dialog.log("x", "warn", "w")
    dialog.log("x", "info", "i")
    text = dialog.get_status_text()
    assert "1 exception" in text
    assert "1 fatal error" in text
    assert "1 error" in text
    assert "1 warning" in text
    assert "1 message" in text


def test_clear_resets_counters() -> None:
    dialog = LogDialog(owner=None)
    dialog.log("x", "error", "e")
    dialog.clear()
    assert dialog.get_error_count() == 0
    assert dialog.get_status_text() == ""


def test_init_registers_sink_and_receives_records() -> None:
    LogDialog.init(owner=None)
    log = DebugLog("pypdfbox.routed")
    log.error("E1")
    log.warn("W1")
    inst = LogDialog.instance()
    assert inst is not None
    assert inst.get_error_count() == 1
    assert inst.get_warn_count() == 1


def test_widget_text_contains_record(tk_root: tk.Tk) -> None:
    dialog = LogDialog(owner=tk_root)
    dialog.log("pypdfbox.routed", "error", "boom")
    dialog.show()
    text_widget = dialog._text
    assert text_widget is not None
    contents = text_widget.get("1.0", "end")
    assert "Error" in contents
    assert "routed" in contents
    assert "boom" in contents


def test_log_label_updates_when_provided(tk_root: tk.Tk) -> None:
    from tkinter import ttk

    label = ttk.Label(tk_root, text="")
    dialog = LogDialog(owner=tk_root, log_label=label)
    dialog.log("x", "error", "e")
    assert "error" in label.cget("text")


# ---- direct exercise of more LogDialog branches -------------------------


def test_set_text_font_height_applies_when_text_widget_exists(
    tk_root: tk.Tk,
) -> None:
    dialog = LogDialog(owner=tk_root)
    dialog.show()  # builds the toplevel + text widget
    dialog.set_text_font_height(11)
    # Re-application must not crash.
    dialog.set_text_font_height(12)


def test_set_visible_false_withdraws(tk_root: tk.Tk) -> None:
    dialog = LogDialog(owner=tk_root)
    dialog.show()
    dialog.set_visible(False)
    # No exception ⇒ withdrawn cleanly.


def test_pack_invokes_idletasks_when_toplevel_exists(tk_root: tk.Tk) -> None:
    dialog = LogDialog(owner=tk_root)
    dialog.show()
    dialog.pack()  # exercises the toplevel-exists branch


def test_pack_when_no_toplevel_is_noop() -> None:
    LogDialog(owner=None).pack()  # must not raise


def test_get_content_pane_returns_toplevel_when_built(tk_root: tk.Tk) -> None:
    dialog = LogDialog(owner=tk_root)
    assert dialog.get_content_pane() is None
    dialog.show()
    assert dialog.get_content_pane() is not None


def test_clear_with_widget_resets_text_widget(tk_root: tk.Tk) -> None:
    from tkinter import ttk

    label = ttk.Label(tk_root, text="seeded")
    dialog = LogDialog(owner=tk_root, log_label=label)
    dialog.show()
    dialog.log("pypdfbox.x", "error", "boom")
    dialog.clear()
    assert dialog.get_error_count() == 0
    text_widget = dialog._text  # noqa: SLF001
    assert text_widget is not None
    assert text_widget.get("1.0", "end-1c") == ""
    assert label.cget("text") == ""


def test_show_after_init_pre_seeded_records(tk_root: tk.Tk) -> None:
    dialog = LogDialog(owner=tk_root)
    dialog.log("pypdfbox.routed", "warn", "w1")
    # ``show`` first build runs the replay loop for pending records.
    dialog.show()
    text_widget = dialog._text  # noqa: SLF001
    assert text_widget is not None
    contents = text_widget.get("1.0", "end")
    assert "w1" in contents


def test_show_with_preset_font_height_applies_to_text(tk_root: tk.Tk) -> None:
    dialog = LogDialog(owner=tk_root)
    dialog.set_text_font_height(15)  # set before show — exercises the
    # ``_text is None`` branch then later the ``apply on build`` branch.
    dialog.show()
    text_widget = dialog._text  # noqa: SLF001
    assert text_widget is not None


def test_log_with_throwable_renders_traceback(tk_root: tk.Tk) -> None:
    dialog = LogDialog(owner=tk_root)
    dialog.show()
    try:
        raise RuntimeError("oh no")
    except RuntimeError as exc:
        dialog.log("pypdfbox.routed", "error", "outer", exc)
    text_widget = dialog._text  # noqa: SLF001
    assert text_widget is not None
    contents = text_widget.get("1.0", "end")
    assert "RuntimeError" in contents
    assert "oh no" in contents


def test_render_record_invalid_level_raises(tk_root: tk.Tk) -> None:
    """Direct exercise of ``_render_record`` with an invalid level.

    ``_render_record`` is normally guarded by ``_bump_counters``; calling
    it directly without bumping covers the ``style is None`` branch.
    """
    dialog = LogDialog(owner=tk_root)
    dialog.show()
    with pytest.raises(ValueError):
        dialog._render_record("name", "unknown", "msg", None)  # noqa: SLF001
