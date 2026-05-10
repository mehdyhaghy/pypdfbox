"""Round-out CLI tests for ``pypdfbox extracttext``.

Hand-written; exercises the rounded-out flag set:

* ``-html``
* ``-md`` (markdown)
* ``-ignoreBeads``
* ``-debug``
* ``-password``
* ``-encoding`` (round-trip an output encoding)
* ``-rotationMagic`` (already covered in upstream tests; smoke here)

PDFs are built in-test (no fixture round-trip needed).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.cos import COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.tools import cli
from pypdfbox.tools.extracttext import (
    _default_output,
    _wrap_html,
    _wrap_md,
    extract_text,
)


def _make_text_pdf(path: Path, payloads: list[str]) -> Path:
    doc = PDDocument()
    try:
        for label in payloads:
            page = PDPage(PDRectangle(0.0, 0.0, 612.0, 792.0))
            stream = COSStream()
            stream.set_data(
                f"BT /F0 12 Tf 100 700 Td ({label}) Tj ET".encode("latin-1")
            )
            page.set_contents(stream)
            doc.add_page(page)
        doc.save(path)
    finally:
        doc.close()
    return path


# ----------------------------------------------------------------- helpers


def test_default_output_extension_html(tmp_path: Path) -> None:
    src = tmp_path / "x.pdf"
    assert _default_output(src, html=True).suffix == ".html"


def test_default_output_extension_md(tmp_path: Path) -> None:
    src = tmp_path / "x.pdf"
    assert _default_output(src, md=True).suffix == ".md"


def test_default_output_extension_txt(tmp_path: Path) -> None:
    src = tmp_path / "x.pdf"
    assert _default_output(src).suffix == ".txt"


def test_wrap_html_escapes_payload() -> None:
    out = _wrap_html("<>&\"alpha")
    assert "&lt;" in out
    assert "&gt;" in out
    assert "&amp;" in out
    assert "alpha" in out
    assert out.startswith("<html>")


def test_wrap_md_uses_fenced_block() -> None:
    out = _wrap_md("alpha")
    assert out.startswith("```\n")
    assert "alpha" in out
    assert out.rstrip().endswith("```")


# ----------------------------------------------------------------- HTML


def test_extracttext_html_writes_html_document(tmp_path: Path) -> None:
    pdf = _make_text_pdf(tmp_path / "src.pdf", ["alpha"])
    out = tmp_path / "out.html"
    rc = cli.run_cli(["extracttext", "-i", str(pdf), "-o", str(out), "-html"])
    assert rc == 0
    text = out.read_text(encoding="utf-8")
    assert text.startswith("<html>")
    assert "alpha" in text
    assert "<pre>" in text


def test_extracttext_html_default_extension(tmp_path: Path) -> None:
    pdf = _make_text_pdf(tmp_path / "x.pdf", ["beta"])
    rc = cli.run_cli(["extracttext", "-i", str(pdf), "-html"])
    assert rc == 0
    expected = pdf.with_suffix(".html")
    assert expected.is_file()
    body = expected.read_text(encoding="utf-8")
    assert "beta" in body


# ----------------------------------------------------------------- Markdown


def test_extracttext_md_writes_fenced_block(tmp_path: Path) -> None:
    pdf = _make_text_pdf(tmp_path / "src.pdf", ["gamma"])
    out = tmp_path / "out.md"
    rc = cli.run_cli(["extracttext", "-i", str(pdf), "-o", str(out), "-md"])
    assert rc == 0
    text = out.read_text(encoding="utf-8")
    assert text.startswith("```")
    assert "gamma" in text


def test_extracttext_md_default_extension(tmp_path: Path) -> None:
    pdf = _make_text_pdf(tmp_path / "y.pdf", ["delta"])
    rc = cli.run_cli(["extracttext", "-i", str(pdf), "-md"])
    assert rc == 0
    expected = pdf.with_suffix(".md")
    assert expected.is_file()


# ----------------------------------------------------------------- ignoreBeads


def test_extracttext_ignore_beads_smoke(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    """``-ignoreBeads`` should be accepted and not change the visible
    text output for a document with no article beads."""
    pdf = _make_text_pdf(tmp_path / "no-beads.pdf", ["epsilon"])
    rc = cli.run_cli(
        ["extracttext", "-i", str(pdf), "-console", "-ignoreBeads"]
    )
    assert rc == 0
    assert "epsilon" in capsys.readouterr().out


def test_extract_text_helper_ignore_beads_kwarg(tmp_path: Path) -> None:
    """The helper accepts ``ignore_beads`` and forwards it to the stripper."""
    import io

    pdf = _make_text_pdf(tmp_path / "kw.pdf", ["zeta"])
    buf = io.StringIO()
    with PDDocument.load(pdf) as doc:
        extract_text(doc, buf, ignore_beads=True)
    assert "zeta" in buf.getvalue()


# ----------------------------------------------------------------- debug


def test_extracttext_debug_emits_stderr_summary(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    pdf = _make_text_pdf(tmp_path / "dbg.pdf", ["theta"])
    rc = cli.run_cli(
        ["extracttext", "-i", str(pdf), "-console", "-debug"]
    )
    assert rc == 0
    captured = capsys.readouterr()
    assert "theta" in captured.out
    assert "debug:" in captured.err
    assert "extracttext finished" in captured.err


# ----------------------------------------------------------------- password


def test_extracttext_password_flag_accepted(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    """``-password`` should be silently accepted on an unencrypted PDF
    (mirrors upstream's empty-password default behavior)."""
    pdf = _make_text_pdf(tmp_path / "open.pdf", ["iota"])
    rc = cli.run_cli(
        ["extracttext", "-i", str(pdf), "-console", "-password", ""]
    )
    assert rc == 0
    assert "iota" in capsys.readouterr().out


# ----------------------------------------------------------------- encoding


def test_extracttext_encoding_latin1_round_trip(tmp_path: Path) -> None:
    """Pick a non-default encoding and ensure the output file decodes
    cleanly in that encoding."""
    pdf = _make_text_pdf(tmp_path / "enc.pdf", ["kappa"])
    out = tmp_path / "out.txt"
    rc = cli.run_cli(
        ["extracttext", "-i", str(pdf), "-o", str(out), "-encoding", "latin-1"]
    )
    assert rc == 0
    assert "kappa" in out.read_text(encoding="latin-1")


# ----------------------------------------------------------------- sort


def test_extracttext_sort_flag_accepted(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    pdf = _make_text_pdf(tmp_path / "sorted.pdf", ["lambda"])
    rc = cli.run_cli(["extracttext", "-i", str(pdf), "-console", "-sort"])
    assert rc == 0
    assert "lambda" in capsys.readouterr().out


# ----------------------------------------------------------------- start/end


def test_extracttext_start_end_page_clamps_range(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    pdf = _make_text_pdf(tmp_path / "p.pdf", ["mu", "nu", "xi"])
    rc = cli.run_cli([
        "extracttext", "-i", str(pdf), "-console",
        "-startPage", "2", "-endPage", "2",
    ])
    assert rc == 0
    out = capsys.readouterr().out
    assert "nu" in out
    assert "mu" not in out
    assert "xi" not in out


# ----------------------------------------------------------------- rotation


def test_extracttext_rotation_magic_smoke(tmp_path: Path) -> None:
    """``-rotationMagic`` runs without crashing on an unrotated page."""
    pdf = _make_text_pdf(tmp_path / "rot.pdf", ["omicron"])
    out = tmp_path / "out.txt"
    rc = cli.run_cli(
        ["extracttext", "-i", str(pdf), "-o", str(out), "-rotationMagic"]
    )
    assert rc == 0
    assert "omicron" in out.read_text(encoding="utf-8")


# ----------------------------------------------------------------- HTML+addFileName


def test_extracttext_html_with_add_file_name(tmp_path: Path) -> None:
    """``-html`` + ``-addFileName`` should embed the path inside the
    wrapped HTML body."""
    pdf = _make_text_pdf(tmp_path / "src.pdf", ["pi"])
    out = tmp_path / "out.html"
    rc = cli.run_cli([
        "extracttext", "-i", str(pdf), "-o", str(out),
        "-html", "-addFileName",
    ])
    assert rc == 0
    body = out.read_text(encoding="utf-8")
    assert "<pre>" in body
    assert str(pdf) in body
    assert "pi" in body
