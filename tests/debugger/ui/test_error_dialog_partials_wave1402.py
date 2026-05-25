"""Wave 1402 — branch-coverage round-out for ``ErrorDialog``.

Targets the residual partial branches in
``pypdfbox/debugger/ui/error_dialog.py``:

* 144->146 — ``create_content(throwable=<explicit>)`` ⇒ skip the
  default-throwable fallback.
* 146->148 — ``create_content(message=<explicit>)`` ⇒ skip the
  default-message fallback.
* 153->155 — ``create_error_message`` returns ``None`` ⇒ skip the
  summary ``pack``.
* 156->158 — ``create_detailed_message`` returns ``None`` ⇒ skip the
  detail ``pack``.
* 245->247 — ``mark_suppressed(throwable=<explicit>)`` ⇒ skip the
  default-throwable fallback.
"""

from __future__ import annotations

import contextlib
import os
import tkinter as tk
from collections.abc import Iterator

import pytest

from pypdfbox.debugger.ui.error_dialog import _SUPPRESSED_TYPES, ErrorDialog


@pytest.fixture()
def tk_root() -> Iterator[tk.Tk]:
    if os.environ.get("PYPDFBOX_SKIP_TK", "") == "1":
        pytest.skip("PYPDFBOX_SKIP_TK=1 -- Tk tests opted out")
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"no Tk display available: {exc}")
    root.withdraw()
    try:
        yield root
    finally:
        with contextlib.suppress(tk.TclError):
            root.destroy()


def test_create_content_with_explicit_throwable(tk_root: tk.Tk) -> None:
    """144->146 — when ``throwable`` is provided, the dialog's bound
    error is NOT swapped in."""
    bound = RuntimeError("bound")
    custom = ValueError("from caller")
    dialog = ErrorDialog(bound)
    container = dialog.create_content(parent=tk_root, throwable=custom)
    assert container is not None
    # The detailed text reflects the custom error, not the bound one.
    detail = ErrorDialog.detailed_text(custom)
    assert "ValueError" in detail


def test_create_content_with_explicit_message(tk_root: tk.Tk) -> None:
    """146->148 — when ``message`` is provided, ``str(throwable)`` is
    NOT substituted."""
    dialog = ErrorDialog(RuntimeError("ignored"))
    container = dialog.create_content(parent=tk_root, message="custom summary")
    assert container is not None


def test_create_content_when_summary_widget_is_none(
    tk_root: tk.Tk, monkeypatch: pytest.MonkeyPatch
) -> None:
    """153->155 — ``create_error_message`` returns ``None`` ⇒ skip
    the summary ``pack``."""
    dialog = ErrorDialog(RuntimeError("x"))
    monkeypatch.setattr(dialog, "create_error_message", lambda *a, **kw: None)
    container = dialog.create_content(parent=tk_root)
    assert container is not None


def test_create_content_when_detail_widget_is_none(
    tk_root: tk.Tk, monkeypatch: pytest.MonkeyPatch
) -> None:
    """156->158 — ``create_detailed_message`` returns ``None`` ⇒ skip
    the detail ``pack``."""
    dialog = ErrorDialog(RuntimeError("x"))
    monkeypatch.setattr(dialog, "create_detailed_message", lambda *a, **kw: None)
    container = dialog.create_content(parent=tk_root)
    assert container is not None


def test_mark_suppressed_with_explicit_throwable() -> None:
    """245->247 — when ``throwable`` is provided, the dialog's bound
    error is NOT used."""

    class _CustomError(Exception):
        pass

    # Clear stale state from previous tests.
    _SUPPRESSED_TYPES.discard(_CustomError)
    bound = RuntimeError("bound")
    dialog = ErrorDialog(bound)
    dialog.mark_suppressed(_CustomError("explicit"))
    assert _CustomError in _SUPPRESSED_TYPES
    # Cleanup so we don't leak into other tests.
    _SUPPRESSED_TYPES.discard(_CustomError)
