"""Tests for :meth:`FileOpenSaveDialog.approve_selection`.

Ports the upstream JFileChooser override that prompts on overwrite when
the dialog is in save mode. Our port returns the validated path (or
``None`` to indicate cancellation) instead of calling Swing's
``cancelSelection`` directly.
"""

from __future__ import annotations

from pathlib import Path

from pypdfbox.debugger.ui.file_open_save_dialog import (
    OPEN_DIALOG,
    SAVE_DIALOG,
    FileOpenSaveDialog,
)


def test_approve_selection_open_dialog_accepts_existing_file(tmp_path: Path) -> None:
    existing = tmp_path / "input.pdf"
    existing.write_bytes(b"%PDF-")
    dlg = FileOpenSaveDialog(parent_ui=None)
    assert dlg.approve_selection(str(existing), dialog_type=OPEN_DIALOG) == str(existing)


def test_approve_selection_save_dialog_prompts_on_overwrite(tmp_path: Path) -> None:
    existing = tmp_path / "out.pdf"
    existing.write_bytes(b"%PDF-")
    dlg = FileOpenSaveDialog(parent_ui=None)
    confirmed = []

    def confirm(path: str) -> bool:
        confirmed.append(path)
        return True

    result = dlg.approve_selection(
        str(existing),
        dialog_type=SAVE_DIALOG,
        confirm_overwrite=confirm,
    )
    assert result == str(existing)
    assert confirmed == [str(existing)]


def test_approve_selection_save_dialog_cancelled_when_user_declines(
    tmp_path: Path,
) -> None:
    existing = tmp_path / "out.pdf"
    existing.write_bytes(b"%PDF-")
    dlg = FileOpenSaveDialog(parent_ui=None)
    assert (
        dlg.approve_selection(
            str(existing),
            dialog_type=SAVE_DIALOG,
            confirm_overwrite=lambda _p: False,
        )
        is None
    )


def test_approve_selection_save_dialog_passes_through_new_path(tmp_path: Path) -> None:
    fresh = tmp_path / "new.pdf"
    dlg = FileOpenSaveDialog(parent_ui=None)
    # No overwrite confirmation needed because the file doesn't exist yet.
    assert dlg.approve_selection(str(fresh), dialog_type=SAVE_DIALOG) == str(fresh)


def test_approve_selection_empty_path_returns_none() -> None:
    dlg = FileOpenSaveDialog(parent_ui=None)
    assert dlg.approve_selection("") is None
    assert dlg.approve_selection(None) is None
