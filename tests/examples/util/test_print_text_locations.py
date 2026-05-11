"""Smoke test for :class:`PrintTextLocations`."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from pypdfbox.examples.util.print_text_locations import PrintTextLocations


def test_run_processes_pages(make_pdf: Callable[..., Path]) -> None:
    src = make_pdf("loc.pdf")
    # Blank pages emit no glyph diagnostics; the call must still complete
    # without raising.
    PrintTextLocations.run(str(src))


def test_main_usage_no_args(capsys) -> None:
    PrintTextLocations.main([])
    err = capsys.readouterr().err
    assert "Usage" in err
