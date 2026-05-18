"""Coverage-boost tests (wave 1351) for the ``if __name__ == "__main__"``
guards on five tool modules.

Each tool ships an ``if __name__ == "__main__": sys.exit(<Class>.main(...))``
trailer that wasn't reachable from in-process tests. ``runpy.run_module``
imports the module under ``run_name="__main__"``, which exercises those
lines without spawning a subprocess (so the coverage tracer counts them).

Covered modules / line ranges:

* ``decompress_objectstreams`` lines 57-58
* ``import_fdf`` lines 85-86
* ``import_xfdf`` lines 77-78
* ``pdf_split`` lines 104-105
* ``write_decoded_doc`` line 113
"""
from __future__ import annotations

import runpy
import sys
from pathlib import Path

import pytest

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


@pytest.mark.parametrize(
    ("module_name", "argv"),
    [
        (
            "pypdfbox.tools.decompress_objectstreams",
            ["decompress_objectstreams", "-i", "__missing__.pdf"],
        ),
        (
            "pypdfbox.tools.import_fdf",
            ["import_fdf", "-i", "__missing__.pdf", "--data", "__missing__.fdf"],
        ),
        (
            "pypdfbox.tools.import_xfdf",
            ["import_xfdf", "-i", "__missing__.pdf", "--data", "__missing__.xfdf"],
        ),
        (
            "pypdfbox.tools.pdf_split",
            ["pdf_split", "-i", "__missing__.pdf"],
        ),
        (
            "pypdfbox.tools.write_decoded_doc",
            ["write_decoded_doc", "__missing__.pdf"],
        ),
    ],
)
def test_module_main_block_dispatches_via_runpy(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    module_name: str,
    argv: list[str],
) -> None:
    """Running each tool module as ``__main__`` triggers the trailer
    ``sys.exit(<Class>.main(sys.argv[1:]))``. Every tool here exits with
    code 4 on a missing input — the OSError → exit-code mapping that the
    other coverage tests already pin. The trailer itself is what's under
    test, so the specific exit code matters less than the SystemExit."""
    monkeypatch.setattr(sys, "argv", argv)
    # Force a fresh execution so the module body and __main__ block both run.
    sys.modules.pop(module_name, None)
    with pytest.raises(SystemExit) as excinfo:
        runpy.run_module(module_name, run_name="__main__")
    capsys.readouterr()
    assert excinfo.value.code == 4
