"""Tests for ``pypdfbox merge``."""
from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.pdmodel import PDDocument
from pypdfbox.tools import cli


def test_merge_two_single_page_pdfs(tmp_path: Path, make_pdf) -> None:
    a = make_pdf("a.pdf", page_count=1)
    b = make_pdf("b.pdf", page_count=1)
    out = tmp_path / "out.pdf"
    rc = cli.run_cli(["merge", "-i", str(a), str(b), "-o", str(out)])
    assert rc == 0
    assert out.is_file()
    with PDDocument.load(out) as merged:
        assert merged.get_number_of_pages() == 2


def test_merge_three_pdfs_preserves_total_pages(
    tmp_path: Path, make_pdf
) -> None:
    a = make_pdf("a.pdf", page_count=2)
    b = make_pdf("b.pdf", page_count=3)
    c = make_pdf("c.pdf", page_count=1)
    out = tmp_path / "out.pdf"
    cli.run_cli(["merge", "-i", str(a), str(b), str(c), "-o", str(out)])
    with PDDocument.load(out) as merged:
        assert merged.get_number_of_pages() == 6


def test_merge_requires_two_inputs(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], make_pdf
) -> None:
    a = make_pdf("a.pdf")
    out = tmp_path / "out.pdf"
    rc = cli.run_cli(["merge", "-i", str(a), "-o", str(out)])
    assert rc == 2
    assert "two input" in capsys.readouterr().out


def test_merge_missing_input(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], make_pdf
) -> None:
    a = make_pdf("a.pdf")
    out = tmp_path / "out.pdf"
    rc = cli.run_cli(
        ["merge", "-i", str(a), str(tmp_path / "ghost.pdf"), "-o", str(out)]
    )
    assert rc == 4
    assert "not a file" in capsys.readouterr().out


def test_merge_long_form_flags(tmp_path: Path, make_pdf) -> None:
    a = make_pdf("a.pdf")
    b = make_pdf("b.pdf")
    out = tmp_path / "out.pdf"
    rc = cli.run_cli(["merge", "--input", str(a), str(b), "--output", str(out)])
    assert rc == 0
    assert out.is_file()
