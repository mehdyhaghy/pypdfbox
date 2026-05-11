"""Smoke test for :class:`ExtractTextByArea`."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from pypdfbox.examples.util.extract_text_by_area import ExtractTextByArea


def test_extract_region_runs(make_pdf: Callable[..., Path]) -> None:
    src = make_pdf("area.pdf")
    text = ExtractTextByArea.extract_region(str(src))
    # Blank pages produce empty text — the call must still complete.
    assert isinstance(text, str)
