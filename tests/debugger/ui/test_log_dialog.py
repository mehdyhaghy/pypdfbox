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
