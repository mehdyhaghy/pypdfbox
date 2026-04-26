"""Dispatcher-level tests: argparse wiring, --help, unknown subcommand."""
from __future__ import annotations

import pytest

from pypdfbox.tools import cli


def test_help_lists_all_subcommands(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        cli.run_cli(["--help"])
    # argparse exits 0 on --help.
    assert excinfo.value.code == 0
    out = capsys.readouterr().out
    for sub in ("info", "merge", "split", "version", "decrypt"):
        assert sub in out


def test_no_subcommand_errors(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        cli.run_cli([])
    assert excinfo.value.code != 0
    err = capsys.readouterr().err
    assert "command" in err.lower() or "required" in err.lower()


def test_unknown_subcommand_errors(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        cli.run_cli(["definitely-not-a-real-subcommand"])
    assert excinfo.value.code != 0
    err = capsys.readouterr().err
    assert "invalid choice" in err.lower() or "argument" in err.lower()


def test_subcommand_help_works(capsys: pytest.CaptureFixture[str]) -> None:
    """Each subcommand must respond to --help with exit 0."""
    for sub in ("info", "merge", "split", "version", "decrypt"):
        with pytest.raises(SystemExit) as excinfo:
            cli.run_cli([sub, "--help"])
        assert excinfo.value.code == 0, f"{sub} --help did not exit 0"
        out = capsys.readouterr().out
        assert sub in out or "usage" in out.lower()


def test_main_calls_sys_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    """`main` must call sys.exit so the shell sees the return code."""
    monkeypatch.setattr("sys.argv", ["pypdfbox", "version"])
    with pytest.raises(SystemExit) as excinfo:
        cli.main()
    assert excinfo.value.code == 0
