"""Smoke test for :class:`DrawPrintTextLocations`."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from pypdfbox.examples.util.draw_print_text_locations import DrawPrintTextLocations


def test_run_blank_pdf(make_pdf: Callable[..., Path]) -> None:
    src = make_pdf("draw.pdf")
    DrawPrintTextLocations.run(str(src))
