from __future__ import annotations

import argparse
import io
from typing import Any

import pytest

from pypdfbox.tools import extracttext, version


def _extracttext_args(**overrides: object) -> argparse.Namespace:
    values: dict[str, object] = {
        "input": "input.pdf",
        "output": None,
        "password": "",
        "encoding": "utf-8",
        "start_page": 1,
        "end_page": 1,
        "sort": False,
        "to_console": True,
        "add_file_name": False,
        "append": False,
        "rotation_magic": False,
        "html": False,
        "md": False,
        "ignore_beads": False,
        "debug": False,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def test_wave732_extracttext_rotation_magic_returns_for_empty_range() -> None:
    output = io.StringIO()

    extracttext._extract_text_rotation_magic(  # noqa: SLF001
        object(),
        output,
        first=4,
        last=3,
        sort=False,
    )

    assert output.getvalue() == ""


def test_wave732_extracttext_rotation_magic_uses_zero_angle_when_none_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, Any]] = []

    class _Collector:
        def set_sort_by_position(self, value: bool) -> None:
            calls.append(("collector_sort", value))

        def set_start_page(self, value: int) -> None:
            calls.append(("collector_start", value))

        def set_end_page(self, value: int) -> None:
            calls.append(("collector_end", value))

        def get_text(self, document: object) -> str:
            calls.append(("collector_text", document))
            return ""

        def get_angles(self) -> set[int]:
            return set()

    class _Stripper:
        def __init__(self, *, target_angle: int) -> None:
            self.target_angle = target_angle
            calls.append(("stripper_angle", target_angle))

        def set_sort_by_position(self, value: bool) -> None:
            calls.append(("stripper_sort", value))

        def set_should_separate_by_beads(self, value: bool) -> None:
            calls.append(("stripper_beads", value))

        def set_start_page(self, value: int) -> None:
            calls.append(("stripper_start", value))

        def set_end_page(self, value: int) -> None:
            calls.append(("stripper_end", value))

        def get_text(self, document: object) -> str:
            calls.append(("stripper_text", document))
            return f"angle={self.target_angle}"

    monkeypatch.setattr(extracttext, "AngleCollector", _Collector)
    monkeypatch.setattr(extracttext, "FilteredTextStripper", _Stripper)
    output = io.StringIO()
    document = object()

    extracttext._extract_text_rotation_magic(  # noqa: SLF001
        document,
        output,
        first=1,
        last=1,
        sort=True,
        ignore_beads=True,
    )

    assert ("stripper_angle", 0) in calls
    assert ("stripper_beads", False) in calls
    assert output.getvalue() == "angle=0"


def test_wave732_extracttext_run_returns_one_for_invalid_password(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    src = tmp_path / "locked.pdf"
    src.write_bytes(b"%PDF-1.4\n")

    def _load(*args: object, **kwargs: object) -> object:
        raise extracttext.InvalidPasswordException("bad password")

    monkeypatch.setattr(extracttext.PDDocument, "load", _load)

    rc = extracttext.run(_extracttext_args(input=str(src), password="secret"))

    assert rc == 1
    assert "bad password" in capsys.readouterr().out


def test_wave732_extracttext_run_returns_one_when_permission_denied(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    src = tmp_path / "denied.pdf"
    src.write_bytes(b"%PDF-1.4\n")
    closed: list[bool] = []

    class _Permission:
        def can_extract_content(self) -> bool:
            return False

    class _Document:
        def get_current_access_permission(self) -> _Permission:
            return _Permission()

        def close(self) -> None:
            closed.append(True)

    monkeypatch.setattr(extracttext.PDDocument, "load", lambda *a, **k: _Document())

    rc = extracttext.run(_extracttext_args(input=str(src)))

    assert rc == 1
    assert closed == [True]
    assert "permission to extract text" in capsys.readouterr().out


def test_wave732_version_project_version_falls_back_when_distribution_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _missing_version(name: str) -> str:
        raise version.metadata.PackageNotFoundError(name)

    monkeypatch.setattr(version.metadata, "version", _missing_version)

    assert version._project_version() == "0.0.0+unknown"  # noqa: SLF001


def test_wave732_version_dependency_versions_returns_empty_when_distribution_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _missing_distribution(name: str) -> object:
        raise version.metadata.PackageNotFoundError(name)

    monkeypatch.setattr(version.metadata, "distribution", _missing_distribution)

    assert version._dependency_versions() == []  # noqa: SLF001


def test_wave732_version_dependency_versions_normalizes_requirements(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Distribution:
        requires = [
            "installed>=1.0; python_version >= '3.10'",
            "missing[extra] >= 2",
            " ; extra == 'test'",
        ]

    def _distribution(name: str) -> _Distribution:
        assert name == "pypdfbox"
        return _Distribution()

    def _dependency_version(name: str) -> str:
        if name == "installed":
            return "9.9"
        raise version.metadata.PackageNotFoundError(name)

    monkeypatch.setattr(version.metadata, "distribution", _distribution)
    monkeypatch.setattr(version.metadata, "version", _dependency_version)

    assert version._dependency_versions() == [  # noqa: SLF001
        ("installed", "9.9"),
        ("missing", "<not installed>"),
    ]


def test_wave732_version_run_prints_empty_dependency_marker(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(version, "_project_version", lambda: "1.2.3")
    monkeypatch.setattr(version, "_dependency_versions", list)

    assert version.run(argparse.Namespace()) == 0

    out = capsys.readouterr().out
    assert "pypdfbox 1.2.3" in out
    assert "Dependencies: (none)" in out


def test_wave732_version_run_prints_dependency_rows(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(version, "_project_version", lambda: "1.2.3")
    monkeypatch.setattr(version, "_dependency_versions", lambda: [("dep", "4.5.6")])

    assert version.run(argparse.Namespace()) == 0

    out = capsys.readouterr().out
    assert "Dependencies:" in out
    assert "  dep 4.5.6" in out
