"""Wave 307 dispatcher hardening tests."""
from __future__ import annotations

import argparse

import pytest

from pypdfbox.tools import cli


def test_wave307_dispatcher_io_errors_go_to_stderr(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(_args: argparse.Namespace) -> int:
        raise OSError("disk full")

    def build_parser() -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(prog="pypdfbox")
        subparsers = parser.add_subparsers(dest="command", required=True)
        subparser = subparsers.add_parser("boom")
        subparser.set_defaults(func=fail)
        return parser

    monkeypatch.setattr(cli, "_build_root_parser", build_parser)

    assert cli.run_cli(["boom"]) == 4

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "boom: I/O error: disk full\n"
