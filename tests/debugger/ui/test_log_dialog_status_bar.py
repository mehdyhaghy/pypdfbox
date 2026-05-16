"""Tests for the promoted :meth:`LogDialog.update_status_bar`.

Mirrors the upstream ``updateStatusBar`` private helper; we expose it
publicly so tests can assert that the bottom-panel label refreshes after
counter manipulation.
"""

from __future__ import annotations

from typing import Any


class _FakeLabel:
    """Stub mimicking the slice of ``tk.Label`` we touch in the dialog."""

    def __init__(self) -> None:
        self.text = ""

    def configure(self, **kwargs: Any) -> None:
        if "text" in kwargs:
            self.text = kwargs["text"]


def _make_dialog() -> tuple[Any, _FakeLabel]:
    from pypdfbox.debugger.ui.log_dialog import LogDialog

    label = _FakeLabel()
    dlg = LogDialog(owner=None, log_label=label)  # type: ignore[arg-type]
    return dlg, label


def test_update_status_bar_writes_summary_to_label() -> None:
    dlg, label = _make_dialog()
    dlg._error_count = 2  # noqa: SLF001
    dlg._warn_count = 1  # noqa: SLF001
    dlg.update_status_bar()
    assert label.text == "2 errors, 1 warning"


def test_update_status_bar_empty_when_no_counters() -> None:
    dlg, label = _make_dialog()
    dlg.update_status_bar()
    assert label.text == ""


def test_update_status_bar_with_exceptions_and_fatals() -> None:
    dlg, label = _make_dialog()
    dlg._exception_count = 3  # noqa: SLF001
    dlg._fatal_count = 1  # noqa: SLF001
    dlg.update_status_bar()
    assert label.text == "3 exceptions, 1 fatal error"


def test_legacy_private_alias_still_works() -> None:
    dlg, label = _make_dialog()
    dlg._warn_count = 4  # noqa: SLF001
    dlg._update_status_bar()  # noqa: SLF001
    assert label.text == "4 warnings"
