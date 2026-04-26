"""Tests for ``pypdfbox split``."""
from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.pdmodel import PDDocument
from pypdfbox.tools import cli


def test_split_one_per_page_default(make_pdf, capsys: pytest.CaptureFixture[str]) -> None:
    pdf = make_pdf("doc.pdf", page_count=3)
    rc = cli.run_cli(["split", "-i", str(pdf)])
    assert rc == 0
    parts = sorted(pdf.parent.glob("doc-*.pdf"))
    assert len(parts) == 3
    for part in parts:
        with PDDocument.load(part) as d:
            assert d.get_number_of_pages() == 1


def test_split_n_per_chunk(make_pdf) -> None:
    pdf = make_pdf("chunked.pdf", page_count=5)
    rc = cli.run_cli(["split", "-i", str(pdf), "-split", "2"])
    assert rc == 0
    parts = sorted(pdf.parent.glob("chunked-*.pdf"))
    # 5 pages, chunks of 2 → 3 outputs (2, 2, 1).
    assert len(parts) == 3
    sizes = [PDDocument.load(p).get_number_of_pages() for p in parts]
    assert sizes == [2, 2, 1]


def test_split_with_page_range(make_pdf) -> None:
    pdf = make_pdf("ranged.pdf", page_count=10)
    cli.run_cli(
        ["split", "-i", str(pdf), "-startPage", "3", "-endPage", "5"]
    )
    parts = sorted(pdf.parent.glob("ranged-*.pdf"))
    # pages 3..5 inclusive = 3 pages, default split=1 → 3 files.
    assert len(parts) == 3


def test_split_custom_prefix(tmp_path: Path, make_pdf) -> None:
    pdf = make_pdf("ignored.pdf", page_count=2)
    cli.run_cli(["split", "-i", str(pdf), "-outputPrefix", "chunk"])
    parts = sorted(pdf.parent.glob("chunk-*.pdf"))
    assert len(parts) == 2


def test_split_zero_split_rejected(
    make_pdf, capsys: pytest.CaptureFixture[str]
) -> None:
    pdf = make_pdf("doc.pdf", page_count=2)
    rc = cli.run_cli(["split", "-i", str(pdf), "-split", "0"])
    assert rc == 2
    assert "must be >= 1" in capsys.readouterr().out


def test_split_empty_range(
    make_pdf, capsys: pytest.CaptureFixture[str]
) -> None:
    pdf = make_pdf("doc.pdf", page_count=3)
    rc = cli.run_cli(
        ["split", "-i", str(pdf), "-startPage", "5", "-endPage", "5"]
    )
    assert rc == 2
    assert "empty page range" in capsys.readouterr().out


def test_split_missing_input(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rc = cli.run_cli(["split", "-i", str(tmp_path / "nope.pdf")])
    assert rc == 4
    assert "not a file" in capsys.readouterr().out
