"""Wave 285 coverage for pdfdebugger malformed object-id inputs."""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from pypdfbox.tools import cli


def test_show_object_rejects_negative_object_number(
    capsys: pytest.CaptureFixture[str], make_pdf: Callable[..., Path]
) -> None:
    pdf = make_pdf(page_count=1)

    rc = cli.run_cli(["pdfdebugger", str(pdf), "--show-object", "-1.0"])

    assert rc == 2
    assert "--show-object expects NUM[.GEN]" in capsys.readouterr().out


def test_object_rejects_negative_generation(
    capsys: pytest.CaptureFixture[str], make_pdf: Callable[..., Path]
) -> None:
    pdf = make_pdf(page_count=1)

    rc = cli.run_cli(["pdfdebugger", str(pdf), "-object", "1", "-1"])

    assert rc == 2
    assert "-object expects non-negative integer NUM [GEN]" in capsys.readouterr().out


def test_dump_stream_rejects_negative_generation(
    capsys: pytest.CaptureFixture[str], make_pdf: Callable[..., Path]
) -> None:
    pdf = make_pdf(page_count=1)

    rc = cli.run_cli(["pdfdebugger", str(pdf), "--dump-stream", "1.-1"])

    assert rc == 2
    assert "--dump-stream expects NUM[.GEN]" in capsys.readouterr().out
