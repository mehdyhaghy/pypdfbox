"""Tests for ``pypdfbox texttopdf`` and the ``create_pdf_from_text`` helper."""
from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.pdmodel import PDDocument, PDRectangle
from pypdfbox.text import PDFTextStripper
from pypdfbox.tools import cli, texttopdf


# ---------------------------------------------------------------------- helpers


def _write_text(path: Path, text: str, *, encoding: str = "utf-8") -> Path:
    path.write_text(text, encoding=encoding)
    return path


def _strip_text(pdf_path: Path) -> str:
    with PDDocument.load(pdf_path) as doc:
        stripper = PDFTextStripper()
        stripper.set_sort_by_position(True)
        return stripper.get_text(doc)


# ---------------------------------------------------------- helper API


def test_create_pdf_from_text_round_trip_single_line(tmp_path: Path) -> None:
    src = _write_text(tmp_path / "in.txt", "hello world\n")
    out = tmp_path / "out.pdf"

    texttopdf.create_pdf_from_text_file(src, out)

    assert out.is_file()
    with PDDocument.load(out) as doc:
        assert doc.get_number_of_pages() == 1
    assert "hello world" in _strip_text(out)


def test_create_pdf_from_text_multiline_one_page(tmp_path: Path) -> None:
    body = "\n".join(f"line number {i}" for i in range(5))
    src = _write_text(tmp_path / "in.txt", body)
    out = tmp_path / "out.pdf"

    texttopdf.create_pdf_from_text_file(src, out)

    with PDDocument.load(out) as doc:
        assert doc.get_number_of_pages() == 1
    extracted = _strip_text(out)
    for i in range(5):
        assert f"line number {i}" in extracted


def test_create_pdf_from_text_overflow_creates_more_pages(tmp_path: Path) -> None:
    # Far more lines than fit on a single Letter page at 10pt — upstream
    # default fits ~70 lines per page; 200 should produce >= 2 pages.
    body = "\n".join(f"row {i}" for i in range(200))
    src = _write_text(tmp_path / "in.txt", body)
    out = tmp_path / "out.pdf"

    texttopdf.create_pdf_from_text_file(src, out)

    with PDDocument.load(out) as doc:
        assert doc.get_number_of_pages() >= 2


def test_create_pdf_from_text_form_feed_forces_page_break(tmp_path: Path) -> None:
    # \f is the upstream form-feed page-break trigger.
    src = _write_text(tmp_path / "in.txt", "before\fafter\n")
    out = tmp_path / "out.pdf"

    texttopdf.create_pdf_from_text_file(src, out)

    with PDDocument.load(out) as doc:
        assert doc.get_number_of_pages() == 2


def test_create_pdf_from_text_empty_input_still_yields_a_page(tmp_path: Path) -> None:
    src = _write_text(tmp_path / "empty.txt", "")
    out = tmp_path / "out.pdf"

    texttopdf.create_pdf_from_text_file(src, out)

    with PDDocument.load(out) as doc:
        # Upstream forces at least one page so the resulting PDF is valid.
        assert doc.get_number_of_pages() == 1


def test_create_pdf_from_text_letter_default_media_box(tmp_path: Path) -> None:
    src = _write_text(tmp_path / "in.txt", "x")
    out = tmp_path / "out.pdf"

    texttopdf.create_pdf_from_text_file(src, out)

    with PDDocument.load(out) as doc:
        mb = doc.get_page(0).get_media_box()
        assert mb.get_width() == pytest.approx(612.0)
        assert mb.get_height() == pytest.approx(792.0)


def test_create_pdf_from_text_a4_media_box(tmp_path: Path) -> None:
    src = _write_text(tmp_path / "in.txt", "x")
    out = tmp_path / "out.pdf"

    texttopdf.create_pdf_from_text_file(src, out, page_size="A4")

    with PDDocument.load(out) as doc:
        mb = doc.get_page(0).get_media_box()
        assert mb.get_width() == pytest.approx(595.0)
        assert mb.get_height() == pytest.approx(842.0)


def test_create_pdf_from_text_landscape_swaps_dimensions(tmp_path: Path) -> None:
    src = _write_text(tmp_path / "in.txt", "x")
    out = tmp_path / "out.pdf"

    texttopdf.create_pdf_from_text_file(
        src, out, page_size="Letter", landscape=True
    )

    with PDDocument.load(out) as doc:
        mb = doc.get_page(0).get_media_box()
        assert mb.get_width() == pytest.approx(792.0)
        assert mb.get_height() == pytest.approx(612.0)


def test_create_pdf_from_text_custom_media_box(tmp_path: Path) -> None:
    src = _write_text(tmp_path / "in.txt", "x")
    out = tmp_path / "out.pdf"

    texttopdf.create_pdf_from_text_file(
        src, out, media_box=PDRectangle(0.0, 0.0, 300.0, 400.0)
    )

    with PDDocument.load(out) as doc:
        mb = doc.get_page(0).get_media_box()
        assert mb.get_width() == pytest.approx(300.0)
        assert mb.get_height() == pytest.approx(400.0)


def test_create_pdf_from_text_negative_line_spacing_rejected(
    tmp_path: Path,
) -> None:
    from pypdfbox.pdmodel.font import PDFontFactory

    doc = PDDocument()
    try:
        with pytest.raises(ValueError, match="line spacing must be positive"):
            texttopdf.create_pdf_from_text(
                doc,
                ["abc"],
                font=PDFontFactory.create_default_font(),
                line_spacing=0.0,
            )
    finally:
        doc.close()


# ---------------------------------------------------------- CLI surface


def test_cli_basic(tmp_path: Path) -> None:
    src = _write_text(tmp_path / "in.txt", "hello cli\n")
    out = tmp_path / "out.pdf"

    rc = cli.run_cli(["texttopdf", "-i", str(src), "-o", str(out)])

    assert rc == 0
    assert out.is_file()
    assert "hello cli" in _strip_text(out)


def test_cli_page_size_a4(tmp_path: Path) -> None:
    src = _write_text(tmp_path / "in.txt", "x\n")
    out = tmp_path / "out.pdf"

    rc = cli.run_cli(
        ["texttopdf", "-i", str(src), "-o", str(out), "-pageSize", "A4"]
    )

    assert rc == 0
    with PDDocument.load(out) as doc:
        mb = doc.get_page(0).get_media_box()
        assert mb.get_width() == pytest.approx(595.0)


def test_cli_landscape(tmp_path: Path) -> None:
    src = _write_text(tmp_path / "in.txt", "x\n")
    out = tmp_path / "out.pdf"

    rc = cli.run_cli(
        ["texttopdf", "-i", str(src), "-o", str(out), "-landscape"]
    )

    assert rc == 0
    with PDDocument.load(out) as doc:
        mb = doc.get_page(0).get_media_box()
        assert mb.get_width() > mb.get_height()


def test_cli_font_size_and_font(tmp_path: Path) -> None:
    src = _write_text(tmp_path / "in.txt", "ABC\n")
    out = tmp_path / "out.pdf"

    rc = cli.run_cli(
        [
            "texttopdf", "-i", str(src), "-o", str(out),
            "-fontSize", "24",
            "-font", "Times-Roman",
        ]
    )

    assert rc == 0
    with PDDocument.load(out) as doc:
        body = doc.get_page(0).get_contents()
        # Tf operator should report 24pt in the content stream.
        assert b"24 Tf" in body


def test_cli_media_box(tmp_path: Path) -> None:
    src = _write_text(tmp_path / "in.txt", "x\n")
    out = tmp_path / "out.pdf"

    rc = cli.run_cli(
        [
            "texttopdf", "-i", str(src), "-o", str(out),
            "-mediaBox", "0", "0", "200", "300",
        ]
    )

    assert rc == 0
    with PDDocument.load(out) as doc:
        mb = doc.get_page(0).get_media_box()
        assert mb.get_width() == pytest.approx(200.0)
        assert mb.get_height() == pytest.approx(300.0)


def test_cli_missing_input_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "out.pdf"
    rc = cli.run_cli(
        ["texttopdf", "-i", str(tmp_path / "ghost.txt"), "-o", str(out)]
    )
    assert rc == 4
    assert "not a file" in capsys.readouterr().out
    assert not out.exists()


def test_cli_stdin_input(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = tmp_path / "out.pdf"
    import io as _io
    monkeypatch.setattr("sys.stdin", _io.StringIO("piped line\n"))

    rc = cli.run_cli(["texttopdf", "-i", "-", "-o", str(out)])

    assert rc == 0
    assert "piped line" in _strip_text(out)
