"""Smoke test for :class:`PrintTextColors`."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from pypdfbox.examples.util.print_text_colors import PrintTextColors


def test_run_runs(make_pdf: Callable[..., Path]) -> None:
    src = make_pdf("colors.pdf")
    PrintTextColors.run(str(src))
