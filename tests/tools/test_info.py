"""Tests for ``pypdfbox info``."""
from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.tools import cli


def test_info_blank_document(capsys: pytest.CaptureFixture[str], make_pdf) -> None:
    pdf = make_pdf(page_count=1)
    rc = cli.run_cli(["info", str(pdf)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Pages: 1" in out
    assert "Encrypted: no" in out
    assert "PDF version" in out


def test_info_multipage(capsys: pytest.CaptureFixture[str], make_pdf) -> None:
    pdf = make_pdf(page_count=4)
    cli.run_cli(["info", str(pdf)])
    out = capsys.readouterr().out
    assert "Pages: 4" in out


def test_info_prints_metadata(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    pdf = tmp_path / "with_meta.pdf"
    doc = PDDocument()
    doc.add_page(PDPage())
    info = doc.get_document_information()
    info.set_title("Hello Title")
    info.set_author("Anne Author")
    info.set_creator("pypdfbox tests")
    doc.save(pdf)
    doc.close()

    cli.run_cli(["info", str(pdf)])
    out = capsys.readouterr().out
    assert "Hello Title" in out
    assert "Anne Author" in out
    assert "pypdfbox tests" in out


def test_info_missing_file(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    target = tmp_path / "does-not-exist.pdf"
    rc = cli.run_cli(["info", str(target)])
    assert rc == 4
    out = capsys.readouterr().out
    assert "not a file" in out
