"""Smoke test for the :class:`CreateCheckBox` example port."""

from __future__ import annotations

from pathlib import Path

from pypdfbox.examples.interactive.form.create_check_box import CreateCheckBox


def test_create_check_box_runs(tmp_path: Path) -> None:
    out = tmp_path / "checkbox.pdf"
    CreateCheckBox.main([str(out)])
    assert out.exists()
    assert out.stat().st_size > 0


def test_create_appearance_stream_helper_lite_port() -> None:
    # The lite port returns ``None`` until the appearance-stream pipeline
    # lands; this guards the public surface so callers know the helper
    # exists even when it's a no-op.
    assert CreateCheckBox.create_appearance_stream(None, None, True, None) is None
