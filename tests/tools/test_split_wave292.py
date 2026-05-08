"""Wave 292 split CLI validation coverage."""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from pypdfbox.tools import cli


def test_split_rejects_zero_start_page(
    make_pdf: Callable[..., Path], capsys: pytest.CaptureFixture[str]
) -> None:
    pdf = make_pdf("zero-start.pdf", page_count=2)

    rc = cli.run_cli(["split", "-i", str(pdf), "-startPage", "0"])

    assert rc == 2
    assert "-startPage must be >= 1" in capsys.readouterr().out


def test_split_rejects_negative_end_page(
    make_pdf: Callable[..., Path], capsys: pytest.CaptureFixture[str]
) -> None:
    pdf = make_pdf("negative-end.pdf", page_count=2)

    rc = cli.run_cli(["split", "-i", str(pdf), "-endPage", "-2"])

    assert rc == 2
    assert "-endPage must be >= 1" in capsys.readouterr().out
