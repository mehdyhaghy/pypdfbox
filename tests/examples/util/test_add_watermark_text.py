"""Smoke test for :class:`AddWatermarkText`."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from pypdfbox.examples.util.add_watermark_text import AddWatermarkText


def test_watermark_runs(make_pdf: Callable[..., Path], tmp_path: Path) -> None:
    src = make_pdf("water.pdf", page_count=2)
    dst = tmp_path / "wm.pdf"
    AddWatermarkText.main([str(src), str(dst), "DRAFT"])
    assert dst.exists()
    assert dst.stat().st_size > 0
