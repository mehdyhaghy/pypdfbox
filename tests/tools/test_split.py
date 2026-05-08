"""Tests for ``pypdfbox split``."""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from pypdfbox.pdmodel import PDDocument
from pypdfbox.tools import cli

MakePdf = Callable[..., Path]


def test_split_one_per_page_default(
    make_pdf: MakePdf,
    capsys: pytest.CaptureFixture[str],
) -> None:
    pdf = make_pdf("doc.pdf", page_count=3)
    rc = cli.run_cli(["split", "-i", str(pdf)])
    assert rc == 0
    parts = sorted(pdf.parent.glob("doc-*.pdf"))
    assert len(parts) == 3
    for part in parts:
        with PDDocument.load(part) as d:
            assert d.get_number_of_pages() == 1


def test_split_n_per_chunk(make_pdf: MakePdf) -> None:
    pdf = make_pdf("chunked.pdf", page_count=5)
    rc = cli.run_cli(["split", "-i", str(pdf), "-split", "2"])
    assert rc == 0
    parts = sorted(pdf.parent.glob("chunked-*.pdf"))
    # 5 pages, chunks of 2 → 3 outputs (2, 2, 1).
    assert len(parts) == 3
    sizes = [PDDocument.load(p).get_number_of_pages() for p in parts]
    assert sizes == [2, 2, 1]


def test_split_with_page_range(make_pdf: MakePdf) -> None:
    pdf = make_pdf("ranged.pdf", page_count=10)
    cli.run_cli(
        ["split", "-i", str(pdf), "-startPage", "3", "-endPage", "5"]
    )
    parts = sorted(pdf.parent.glob("ranged-*.pdf"))
    # Upstream parity: a bare range with no -split emits the entire range
    # as a SINGLE output file (PDFSplit.java sets splitAtPage=numberOfPages
    # or endPage when start/end are present and split is unset).
    assert len(parts) == 1
    with PDDocument.load(parts[0]) as d:
        assert d.get_number_of_pages() == 3


def test_split_with_page_range_and_explicit_split(make_pdf: MakePdf) -> None:
    pdf = make_pdf("rangesplit.pdf", page_count=10)
    cli.run_cli(
        [
            "split", "-i", str(pdf),
            "-startPage", "3", "-endPage", "8",
            "-split", "2",
        ]
    )
    parts = sorted(pdf.parent.glob("rangesplit-*.pdf"))
    # Pages 3..8 inclusive = 6 pages, split=2 → 3 files of 2 pages each.
    assert len(parts) == 3
    sizes = [PDDocument.load(p).get_number_of_pages() for p in parts]
    assert sizes == [2, 2, 2]


def test_split_only_start_page(make_pdf: MakePdf) -> None:
    pdf = make_pdf("startonly.pdf", page_count=5)
    cli.run_cli(["split", "-i", str(pdf), "-startPage", "3"])
    parts = sorted(pdf.parent.glob("startonly-*.pdf"))
    # startPage=3 only, no -split: pages 3..5 = single file with 3 pages.
    assert len(parts) == 1
    with PDDocument.load(parts[0]) as d:
        assert d.get_number_of_pages() == 3


def test_split_password_flag_accepts_unencrypted_doc(make_pdf: MakePdf) -> None:
    pdf = make_pdf("nopwd.pdf", page_count=2)
    rc = cli.run_cli(
        ["split", "-i", str(pdf), "-password", "ignored"]
    )
    # PDDocument.load tolerates a password on an unencrypted doc; verify
    # the flag is accepted end-to-end.
    assert rc == 0
    parts = sorted(pdf.parent.glob("nopwd-*.pdf"))
    assert len(parts) == 2


def test_split_password_long_form(make_pdf: MakePdf) -> None:
    pdf = make_pdf("nopwd2.pdf", page_count=2)
    rc = cli.run_cli(
        ["split", "-i", str(pdf), "--password", "ignored"]
    )
    assert rc == 0
    parts = sorted(pdf.parent.glob("nopwd2-*.pdf"))
    assert len(parts) == 2


def test_split_custom_prefix(tmp_path: Path, make_pdf: MakePdf) -> None:
    pdf = make_pdf("ignored.pdf", page_count=2)
    cli.run_cli(["split", "-i", str(pdf), "-outputPrefix", "chunk"])
    parts = sorted(pdf.parent.glob("chunk-*.pdf"))
    assert len(parts) == 2


def test_split_custom_prefix_long_form(tmp_path: Path, make_pdf: MakePdf) -> None:
    pdf = make_pdf("ignored.pdf", page_count=2)
    rc = cli.run_cli(["split", "-i", str(pdf), "--outputPrefix", "chunk"])
    assert rc == 0
    parts = sorted(pdf.parent.glob("chunk-*.pdf"))
    assert len(parts) == 2


def test_split_zero_split_rejected(
    make_pdf: MakePdf, capsys: pytest.CaptureFixture[str]
) -> None:
    pdf = make_pdf("doc.pdf", page_count=2)
    rc = cli.run_cli(["split", "-i", str(pdf), "-split", "0"])
    assert rc == 2
    assert "must be >= 1" in capsys.readouterr().out


def test_split_empty_range(
    make_pdf: MakePdf, capsys: pytest.CaptureFixture[str]
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
