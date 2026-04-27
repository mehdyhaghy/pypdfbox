"""Tests for ``pypdfbox extracttext`` and the ``extract_text`` helper."""
from __future__ import annotations

import io
from pathlib import Path

import pytest

from pypdfbox.cos import COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.tools import cli
from pypdfbox.tools.extracttext import extract_text


# ----------------------------------------------------------------- helpers


def _make_page_with_stream(doc: PDDocument, content: bytes) -> PDPage:
    page = PDPage(PDRectangle(0.0, 0.0, 612.0, 792.0))
    stream = COSStream()
    stream.set_data(content)
    page.set_contents(stream)
    doc.add_page(page)
    return page


def _build_text_pdf(path: Path, payloads: list[str]) -> Path:
    """Build a PDF where each ``payloads[i]`` is the literal string drawn
    on page ``i+1``. Mirrors the helper used in the stripper tests."""
    doc = PDDocument()
    try:
        for label in payloads:
            content = (
                f"BT /F0 12 Tf 100 700 Td ({label}) Tj ET"
            ).encode("latin-1")
            _make_page_with_stream(doc, content)
        doc.save(path)
    finally:
        doc.close()
    return path


# --------------------------------------------------------------- extract_text


def test_extract_text_helper_writes_to_writer(tmp_path: Path) -> None:
    pdf = _build_text_pdf(tmp_path / "two.pdf", ["alpha", "beta"])
    buf = io.StringIO()
    with PDDocument.load(pdf) as doc:
        extract_text(doc, buf)
    text = buf.getvalue()
    assert "alpha" in text
    assert "beta" in text


def test_extract_text_helper_respects_page_range(tmp_path: Path) -> None:
    pdf = _build_text_pdf(tmp_path / "three.pdf", ["one", "two", "three"])
    buf = io.StringIO()
    with PDDocument.load(pdf) as doc:
        extract_text(doc, buf, start_page=2, end_page=2)
    text = buf.getvalue()
    assert "two" in text
    assert "one" not in text
    assert "three" not in text


# --------------------------------------------------------------- CLI: console


def test_extracttext_cli_console_emits_text(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    pdf = _build_text_pdf(tmp_path / "console.pdf", ["greetings"])
    rc = cli.run_cli(["extracttext", "-i", str(pdf), "-console"])
    assert rc == 0
    assert "greetings" in capsys.readouterr().out


def test_extracttext_cli_add_filename_prefixes_path(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    pdf = _build_text_pdf(tmp_path / "named.pdf", ["payload"])
    rc = cli.run_cli(
        ["extracttext", "-i", str(pdf), "-console", "-addFileName"]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert f"PDF file: {pdf}" in out
    assert "payload" in out


# --------------------------------------------------------------- CLI: file out


def test_extracttext_cli_writes_to_outfile(tmp_path: Path) -> None:
    pdf = _build_text_pdf(tmp_path / "src.pdf", ["bodytext"])
    out = tmp_path / "out.txt"
    rc = cli.run_cli(["extracttext", "-i", str(pdf), "-o", str(out)])
    assert rc == 0
    assert out.is_file()
    assert "bodytext" in out.read_text(encoding="utf-8")


def test_extracttext_cli_default_outfile_path(tmp_path: Path) -> None:
    pdf = _build_text_pdf(tmp_path / "auto.pdf", ["defaulted"])
    rc = cli.run_cli(["extracttext", "-i", str(pdf)])
    assert rc == 0
    expected = pdf.with_suffix(".txt")
    assert expected.is_file()
    assert "defaulted" in expected.read_text(encoding="utf-8")


def test_extracttext_cli_append_mode(tmp_path: Path) -> None:
    pdf1 = _build_text_pdf(tmp_path / "a.pdf", ["alpha"])
    pdf2 = _build_text_pdf(tmp_path / "b.pdf", ["beta"])
    out = tmp_path / "joined.txt"
    rc1 = cli.run_cli(["extracttext", "-i", str(pdf1), "-o", str(out)])
    assert rc1 == 0
    rc2 = cli.run_cli(
        ["extracttext", "-i", str(pdf2), "-o", str(out), "-append"]
    )
    assert rc2 == 0
    text = out.read_text(encoding="utf-8")
    assert "alpha" in text
    assert "beta" in text


# --------------------------------------------------------------- CLI: ranges


def test_extracttext_cli_start_end_page(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    pdf = _build_text_pdf(tmp_path / "pages.pdf", ["uno", "due", "tre"])
    rc = cli.run_cli([
        "extracttext", "-i", str(pdf), "-console",
        "-startPage", "2", "-endPage", "2",
    ])
    assert rc == 0
    out = capsys.readouterr().out
    assert "due" in out
    assert "uno" not in out
    assert "tre" not in out


def test_extracttext_cli_sort_flag_accepted(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    pdf = _build_text_pdf(tmp_path / "sort.pdf", ["sortable"])
    rc = cli.run_cli(["extracttext", "-i", str(pdf), "-console", "-sort"])
    assert rc == 0
    assert "sortable" in capsys.readouterr().out


# --------------------------------------------------------------- CLI: errors


def test_extracttext_cli_missing_input(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    rc = cli.run_cli(
        ["extracttext", "-i", str(tmp_path / "nope.pdf"), "-console"]
    )
    assert rc == 4
    assert "not a file" in capsys.readouterr().out


def test_extracttext_cli_encoding_default_utf8(tmp_path: Path) -> None:
    pdf = _build_text_pdf(tmp_path / "enc.pdf", ["ascii"])
    out = tmp_path / "enc.txt"
    rc = cli.run_cli(
        ["extracttext", "-i", str(pdf), "-o", str(out), "-encoding", "UTF-8"]
    )
    assert rc == 0
    assert "ascii" in out.read_text(encoding="utf-8")
