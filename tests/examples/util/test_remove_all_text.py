"""Smoke test for :class:`RemoveAllText`."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from pypdfbox.examples.util.remove_all_text import RemoveAllText


def test_strip_blank_pdf(make_pdf: Callable[..., Path], tmp_path: Path) -> None:
    # Blank pages have no text to strip, but the strip pipeline must
    # still produce a valid output file.
    src = make_pdf("strip.pdf")
    dst = tmp_path / "stripped.pdf"
    RemoveAllText.strip(str(src), str(dst))
    assert dst.exists()
    assert dst.stat().st_size > 0
