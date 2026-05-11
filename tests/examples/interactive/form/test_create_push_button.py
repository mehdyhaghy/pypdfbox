"""Smoke test for :class:`CreatePushButton`."""

from __future__ import annotations

from pathlib import Path

from pypdfbox.examples.interactive.form.create_push_button import CreatePushButton


def test_create_push_button_runs(tmp_path: Path) -> None:
    out = tmp_path / "pushbutton.pdf"
    CreatePushButton.main([str(out)])
    assert out.exists()
    assert out.stat().st_size > 0
