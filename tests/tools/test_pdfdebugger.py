"""Tests for ``pypdfbox pdfdebugger`` (lite CLI replacement for upstream's
Swing-based ``PDFDebugger``)."""
from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.tools import cli


def test_summary_default_mode(capsys: pytest.CaptureFixture[str], make_pdf) -> None:
    pdf = make_pdf(page_count=1)
    rc = cli.run_cli(["pdfdebugger", str(pdf)])
    assert rc == 0
    out = capsys.readouterr().out
    assert f"File: {pdf}" in out
    assert "Pages: 1" in out
    assert "Encrypted: no" in out
    # Catalog Type is /Catalog and Pages is an indirect ref or inline dict.
    assert "Catalog /Type: /Catalog" in out
    assert "Trailer keys:" in out
    # Trailer always carries /Root and /Size for a saved doc.
    assert "/Root" in out
    assert "/Size" in out


def test_trailer_dump(capsys: pytest.CaptureFixture[str], make_pdf) -> None:
    pdf = make_pdf(page_count=2)
    rc = cli.run_cli(["pdfdebugger", str(pdf), "-trailer"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Trailer:" in out
    assert "<<" in out and ">>" in out
    assert "/Root" in out
    assert "/Size" in out


def test_page_dump_prints_type_and_pages_marker(
    capsys: pytest.CaptureFixture[str], make_pdf
) -> None:
    pdf = make_pdf(page_count=3)
    rc = cli.run_cli(["pdfdebugger", str(pdf), "-page", "1"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Page 1:" in out
    assert "/Type" in out
    assert "/Page" in out
    # MediaBox is always written for newly-created pages.
    assert "/MediaBox" in out


def test_page_index_out_of_range(capsys: pytest.CaptureFixture[str], make_pdf) -> None:
    pdf = make_pdf(page_count=1)
    rc = cli.run_cli(["pdfdebugger", str(pdf), "-page", "5"])
    assert rc == 4
    out = capsys.readouterr().out
    assert "out of range" in out


def test_object_dump_for_catalog(
    capsys: pytest.CaptureFixture[str], make_pdf
) -> None:
    pdf = make_pdf(page_count=1)
    # Find the catalog's object key via a real load.
    with PDDocument.load(pdf) as doc:
        cos_doc = doc.get_document()
        trailer = cos_doc.get_trailer()
        assert trailer is not None
        # /Root is stored as a COSObject indirect ref in the trailer.
        from pypdfbox.cos import COSName, COSObject

        root_entry = trailer.get_item(COSName.ROOT)  # type: ignore[attr-defined]
        assert isinstance(root_entry, COSObject)
        num = root_entry.object_number
        gen = root_entry.generation_number

    rc = cli.run_cli(["pdfdebugger", str(pdf), "-object", str(num), str(gen)])
    assert rc == 0
    out = capsys.readouterr().out
    assert f"Object {num} {gen} R:" in out
    assert "/Type" in out
    assert "/Catalog" in out


def test_object_not_in_pool(capsys: pytest.CaptureFixture[str], make_pdf) -> None:
    pdf = make_pdf(page_count=1)
    rc = cli.run_cli(["pdfdebugger", str(pdf), "-object", "9999", "0"])
    assert rc == 4
    out = capsys.readouterr().out
    assert "not in pool" in out


def test_tree_dump_lists_objects(
    capsys: pytest.CaptureFixture[str], make_pdf
) -> None:
    pdf = make_pdf(page_count=2)
    rc = cli.run_cli(["pdfdebugger", str(pdf), "-tree"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Object pool" in out
    # Should mention the catalog and at least one page.
    assert "/Catalog" in out
    assert "/Page" in out


def test_missing_file(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    target = tmp_path / "does-not-exist.pdf"
    rc = cli.run_cli(["pdfdebugger", str(target)])
    assert rc == 4
    out = capsys.readouterr().out
    assert "not a file" in out


def test_mutually_exclusive_flags_rejected(
    capsys: pytest.CaptureFixture[str], make_pdf
) -> None:
    pdf = make_pdf(page_count=1)
    with pytest.raises(SystemExit):
        cli.run_cli(["pdfdebugger", str(pdf), "-trailer", "-tree"])
