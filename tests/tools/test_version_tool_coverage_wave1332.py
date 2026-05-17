"""Wave 1332 — coverage boost for ``pypdfbox.tools.version_tool``.

Targets the ``__version__`` fallback branch (returns ``"unknown"``) and the
``main`` static entry point so the module reaches >=95%.
"""

from __future__ import annotations

import runpy
import sys

import pytest

import pypdfbox
from pypdfbox.tools import version_tool
from pypdfbox.tools.version_tool import Version


def test_spec_qualified_name_is_pypdfbox() -> None:
    assert Version().spec_qualified_name == "pypdfbox"


def test_get_version_returns_known_version() -> None:
    v = Version()
    out = v.get_version()
    assert isinstance(out, list)
    assert len(out) == 1
    assert out[0].startswith("pypdfbox [")
    assert out[0].endswith("]")


def test_get_version_returns_unknown_when_version_attr_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delattr(pypdfbox, "__version__", raising=False)
    assert Version().get_version() == ["unknown"]


def test_call_writes_version_to_stdout_and_returns_zero(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc = Version().call()
    out = capsys.readouterr().out
    assert rc == 0
    assert out.endswith("\n")
    assert ("pypdfbox" in out) or ("unknown" in out)


def test_main_with_default_args_returns_zero(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc = Version.main()
    capsys.readouterr()
    assert rc == 0


def test_main_with_explicit_args_returns_zero(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc = Version.main(["--ignored"])
    capsys.readouterr()
    assert rc == 0


def test_module_executed_as_main_invokes_sys_exit(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(sys, "argv", ["version_tool"])
    with pytest.raises(SystemExit) as excinfo:
        runpy.run_module(version_tool.__name__, run_name="__main__")
    capsys.readouterr()
    assert excinfo.value.code == 0
