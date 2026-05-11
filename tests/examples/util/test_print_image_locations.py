"""Smoke test for :class:`PrintImageLocations`."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from pypdfbox.examples.util.print_image_locations import PrintImageLocations


def test_run_blank_pdf(make_pdf: Callable[..., Path]) -> None:
    # Blank pages contain no images so the example just emits the
    # "Processing page" header for each page — the call must complete
    # without raising.
    src = make_pdf("imgs.pdf", page_count=2)
    PrintImageLocations.run(str(src))
