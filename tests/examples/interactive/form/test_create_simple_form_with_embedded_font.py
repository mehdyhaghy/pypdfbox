"""Smoke test for :class:`CreateSimpleFormWithEmbeddedFont`."""

from __future__ import annotations

from pathlib import Path

from pypdfbox.examples.interactive.form.create_simple_form_with_embedded_font import (
    CreateSimpleFormWithEmbeddedFont,
)


def test_create_simple_form_with_embedded_font_runs(tmp_path: Path) -> None:
    out = tmp_path / "embed.pdf"
    CreateSimpleFormWithEmbeddedFont.main([str(out)])
    assert out.exists()
    assert out.stat().st_size > 0
