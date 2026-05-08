"""Wave 315 pdfdebugger CLI validation coverage."""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from pypdfbox.tools import cli


def test_wave315_pdfdebugger_rejects_negative_depth(
    capsys: pytest.CaptureFixture[str], make_pdf: Callable[..., Path]
) -> None:
    pdf = make_pdf(page_count=1)

    rc = cli.run_cli(["pdfdebugger", str(pdf), "--depth", "-1"])

    assert rc == 2
    assert "--depth must be >= 0" in capsys.readouterr().out
