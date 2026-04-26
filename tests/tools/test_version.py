"""Tests for ``pypdfbox version``."""
from __future__ import annotations

import platform
import sys

import pytest

from pypdfbox.tools import cli, version


def test_version_command_succeeds(capsys: pytest.CaptureFixture[str]) -> None:
    rc = cli.run_cli(["version"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "pypdfbox" in out
    assert "Python" in out


def test_version_includes_python_version(capsys: pytest.CaptureFixture[str]) -> None:
    cli.run_cli(["version"])
    out = capsys.readouterr().out
    py_short = sys.version.split()[0]
    assert py_short in out


def test_version_marks_python_implementation(capsys: pytest.CaptureFixture[str]) -> None:
    cli.run_cli(["version"])
    out = capsys.readouterr().out
    assert platform.python_implementation() in out


def test_version_dependency_section_present(capsys: pytest.CaptureFixture[str]) -> None:
    cli.run_cli(["version"])
    out = capsys.readouterr().out
    # Either "Dependencies: (none)" or per-dep lines must appear.
    assert "Dependencies" in out


def test_project_version_helper_returns_string() -> None:
    v = version._project_version()
    assert isinstance(v, str)
    assert v  # non-empty
