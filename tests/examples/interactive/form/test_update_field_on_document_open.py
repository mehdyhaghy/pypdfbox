"""Smoke test for :class:`UpdateFieldOnDocumentOpen`."""

from __future__ import annotations

from pathlib import Path

from pypdfbox.examples.interactive.form.create_simple_form import CreateSimpleForm
from pypdfbox.examples.interactive.form.update_field_on_document_open import (
    UpdateFieldOnDocumentOpen,
)


def test_attach_open_action_runs(tmp_path: Path) -> None:
    src = tmp_path / "form.pdf"
    CreateSimpleForm.create(str(src))
    dst = tmp_path / "open.pdf"
    UpdateFieldOnDocumentOpen.attach_open_action(str(src), str(dst))
    assert dst.exists()
    assert dst.stat().st_size > 0
