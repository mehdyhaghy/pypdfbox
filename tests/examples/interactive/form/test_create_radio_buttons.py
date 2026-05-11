"""Smoke test for :class:`CreateRadioButtons`."""

from __future__ import annotations

from pathlib import Path

from pypdfbox.examples.interactive.form.create_radio_buttons import CreateRadioButtons


def test_create_radio_buttons_runs(tmp_path: Path) -> None:
    out = tmp_path / "radio.pdf"
    CreateRadioButtons.main([str(out)])
    assert out.exists()
    assert out.stat().st_size > 0


def test_create_appearance_stream_lite() -> None:
    assert CreateRadioButtons.create_appearance_stream(None, None, True) is None
