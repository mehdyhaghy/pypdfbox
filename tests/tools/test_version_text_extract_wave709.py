from __future__ import annotations

import argparse
import io
from pathlib import Path
from typing import Any

import pytest

from pypdfbox.pdmodel import PDDocument, PDRectangle
from pypdfbox.pdmodel.font import PDFontFactory
from pypdfbox.pdmodel.font.pd_font import PDFont
from pypdfbox.pdmodel.font.pd_font_descriptor import PDFontDescriptor
from pypdfbox.tools import extracttext, texttopdf, version


def test_version_project_version_falls_back_when_distribution_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _missing_version(name: str) -> str:
        raise version.metadata.PackageNotFoundError(name)

    monkeypatch.setattr(version.metadata, "version", _missing_version)

    assert version._project_version() == "0.0.0+unknown"  # noqa: SLF001


def test_version_dependency_versions_handle_empty_and_missing_distribution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _missing_distribution(name: str) -> object:
        raise version.metadata.PackageNotFoundError(name)

    monkeypatch.setattr(version.metadata, "distribution", _missing_distribution)

    assert version._dependency_versions() == []  # noqa: SLF001


def test_version_dependency_versions_normalize_requirements(
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


def test_version_run_prints_none_when_dependency_list_empty(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(version, "_project_version", lambda: "1.2.3")
    monkeypatch.setattr(version, "_dependency_versions", list)

    assert version.run(argparse.Namespace()) == 0

    out = capsys.readouterr().out
    assert "pypdfbox 1.2.3" in out
    assert "Dependencies: (none)" in out


def test_texttopdf_font_bbox_height_uses_descriptor_bbox() -> None:
    font = PDFont()
    descriptor = PDFontDescriptor()
    descriptor.set_font_bounding_box(PDRectangle(0.0, -4.0, 10.0, 16.0))
    font.set_font_descriptor(descriptor)

    assert texttopdf._font_bbox_height(font) == pytest.approx(20.0)  # noqa: SLF001


def test_texttopdf_font_bbox_height_falls_back_without_descriptor() -> None:
    assert texttopdf._font_bbox_height(PDFont()) == pytest.approx(1000.0)  # noqa: SLF001


def test_texttopdf_string_width_empty_string_is_zero() -> None:
    assert texttopdf._string_width_units(PDFontFactory.create_default_font(), "") == 0.0  # noqa: SLF001


def test_texttopdf_lookahead_trims_form_feed_before_width_check() -> None:
    doc = PDDocument()
    try:
        texttopdf.create_pdf_from_text(
            doc,
            ["alpha beta\fgamma"],
            font=PDFontFactory.create_default_font(),
        )

        assert doc.get_number_of_pages() == 2
    finally:
        doc.close()


def test_extracttext_rotation_magic_returns_when_range_is_empty() -> None:
    output = io.StringIO()

    extracttext._extract_text_rotation_magic(  # noqa: SLF001
        object(), output, first=3, last=2, sort=False
    )

    assert output.getvalue() == ""


def test_extracttext_rotation_magic_runs_zero_angle_when_collector_finds_none(
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
            self.ignore_beads = False
            calls.append(("stripper_angle", target_angle))

        def set_sort_by_position(self, value: bool) -> None:
            calls.append(("stripper_sort", value))

        def set_should_separate_by_beads(self, value: bool) -> None:
            self.ignore_beads = not value
            calls.append(("stripper_beads", value))

        def set_start_page(self, value: int) -> None:
            calls.append(("stripper_start", value))

        def set_end_page(self, value: int) -> None:
            calls.append(("stripper_end", value))

        def get_text(self, document: object) -> str:
            calls.append(("stripper_text", document))
            return f"angle={self.target_angle};ignore={self.ignore_beads}"

    monkeypatch.setattr(extracttext, "AngleCollector", _Collector)
    monkeypatch.setattr(extracttext, "FilteredTextStripper", _Stripper)
    output = io.StringIO()
    document = object()

    extracttext._extract_text_rotation_magic(  # noqa: SLF001
        document, output, first=1, last=1, sort=True, ignore_beads=True
    )

    assert ("stripper_angle", 0) in calls
    assert ("stripper_beads", False) in calls
    assert output.getvalue() == "angle=0;ignore=True"


def test_extracttext_run_returns_one_when_password_is_invalid(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    src = tmp_path / "locked.pdf"
    src.write_bytes(b"%PDF-1.4\n")

    def _load(*args: object, **kwargs: object) -> object:
        raise extracttext.InvalidPasswordException("bad password")

    monkeypatch.setattr(extracttext.PDDocument, "load", _load)

    rc = extracttext.run(
        argparse.Namespace(
            input=str(src),
            output=None,
            password="secret",
            encoding="utf-8",
            start_page=1,
            end_page=1,
            sort=False,
            to_console=True,
            add_file_name=False,
            append=False,
            rotation_magic=False,
            html=False,
            md=False,
            ignore_beads=False,
            debug=False,
        )
    )

    assert rc == 1
    assert "bad password" in capsys.readouterr().out


def test_extracttext_run_returns_one_when_permissions_deny_extraction(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
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

    rc = extracttext.run(
        argparse.Namespace(
            input=str(src),
            output=None,
            password="",
            encoding="utf-8",
            start_page=1,
            end_page=1,
            sort=False,
            to_console=True,
            add_file_name=False,
            append=False,
            rotation_magic=False,
            html=False,
            md=False,
            ignore_beads=False,
            debug=False,
        )
    )

    assert rc == 1
    assert closed == [True]
    assert "permission to extract text" in capsys.readouterr().out
