"""Live Apache PDFBox parity for the ``PDFMerger`` CLI tool — the end-to-end
multi-file merge surface (``org.apache.pdfbox.tools.PDFMerger`` vs pypdfbox's
``merge`` subcommand in ``pypdfbox.tools.cli``).

The companion ``tests/multipdf/oracle/test_merge_oracle.py`` already pins the
``PDFMergerUtility.merge_documents`` *API* path (merged AcroForm / outline /
named-dest reconciliation). This module instead drives the **CLI tool** on
THREE-or-more inputs, exactly as a shell invocation would:

    PDFMerger -i in1.pdf in2.pdf in3.pdf -o out.pdf      (upstream, via probe)
    pypdfbox merge -i in1.pdf in2.pdf in3.pdf -o out.pdf (pypdfbox, via run_cli)

Both flag spellings are identical (upstream picocli ``-i/--input`` multi-value +
``-o/--output``; pypdfbox argparse ``-i ... nargs='+'`` + ``-o``), so the same
argv shape exercises both tools.

The parity claim:

* both tools exit 0;
* the merged page count equals the sum of the input page counts (2 + 1 + 3 = 6);
* the per-page extracted text matches in merged page order (inputs concatenated
  in CLI order) — a dropped, duplicated, or reordered page shows up immediately;
* the pypdfbox output passes ``qpdf --check``.

Source PDFs are built through pypdfbox so the inputs are byte-identical on both
sides of the comparison. Object-count / xref style is deliberately NOT compared
(documented writer-strategy difference; see the pdfwriter oracle module).
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.pdmodel.common import PDRectangle
from pypdfbox.pdmodel.font.pd_font_factory import PDFontFactory
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream
from pypdfbox.tools import cli
from tests.oracle.harness import requires_oracle, run_probe_text

_QPDF = shutil.which("qpdf")
_requires_qpdf = pytest.mark.skipif(
    _QPDF is None, reason="qpdf binary not on PATH (brew install qpdf)"
)


def _text_page(doc: PDDocument, message: str) -> None:
    """Append a Letter page to ``doc`` showing ``message`` so PDFTextStripper
    recovers it. Uses the standard-14 Helvetica default font (no embedding)."""
    page = PDPage(PDRectangle.LETTER)
    doc.add_page(page)
    font = PDFontFactory.create_default_font()
    cs = PDPageContentStream(doc, page)
    cs.begin_text()
    cs.set_font(font, 12)
    cs.new_line_at_offset(72, 700)
    cs.show_text(message)
    cs.end_text()
    cs.close()


def _build_source_set(out_dir: Path) -> tuple[list[Path], list[str]]:
    """Build three controlled source PDFs and return (paths, expected page text).

    * ``a.pdf`` — two pages: "ALPHA one", "ALPHA two".
    * ``b.pdf`` — one page: "BRAVO solo".
    * ``c.pdf`` — three pages: "CHARLIE i", "CHARLIE ii", "CHARLIE iii".

    Total = 6 pages; the expected merged page-text order is the concatenation
    of the per-file page text in CLI order.
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    spec: list[tuple[str, list[str]]] = [
        ("a.pdf", ["ALPHA one", "ALPHA two"]),
        ("b.pdf", ["BRAVO solo"]),
        ("c.pdf", ["CHARLIE i", "CHARLIE ii", "CHARLIE iii"]),
    ]

    paths: list[Path] = []
    expected_text: list[str] = []
    for name, messages in spec:
        path = out_dir / name
        doc = PDDocument()
        try:
            for message in messages:
                _text_page(doc, message)
            doc.save(str(path))
        finally:
            doc.close()
        paths.append(path)
        expected_text.extend(messages)
    return paths, expected_text


def _qpdf_check(path: Path) -> tuple[int, str]:
    """``(returncode, combined output)`` from ``qpdf --check``. rc <= 3 is
    structurally valid (3 = warnings only)."""
    proc = subprocess.run(
        [str(_QPDF), "--check", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def _read_py_merge(path: Path) -> tuple[int, list[str]]:
    """Reload a pypdfbox-merged document and read (page count, per-page text)."""
    from pypdfbox.text.pdf_text_stripper import PDFTextStripper

    doc = PDDocument.load(path)
    try:
        total = doc.get_number_of_pages()
        stripper = PDFTextStripper()
        page_text: list[str] = []
        for i in range(total):
            stripper.set_start_page(i + 1)
            stripper.set_end_page(i + 1)
            page_text.append(stripper.get_text(doc).strip())
        return total, page_text
    finally:
        doc.close()


@requires_oracle
@_requires_qpdf
def test_merge_tool_three_inputs_matches_pdfbox(tmp_path: Path) -> None:
    """Merge three controlled source PDFs (2 + 1 + 3 = 6 pages) through the
    upstream ``PDFMerger`` CLI and through pypdfbox's ``merge`` CLI; the page
    count, page order, and per-page text must agree, and the pypdfbox output
    must be qpdf-valid."""
    sources, expected_text = _build_source_set(tmp_path / "src")

    # Upstream PDFMerger CLI (picocli) on the three inputs.
    java_out = tmp_path / "java_merged.pdf"
    java_raw = run_probe_text(
        "MergeToolProbe", str(java_out), *[str(s) for s in sources]
    )
    java = json.loads(java_raw)

    assert java["exitCode"] == 0, f"upstream PDFMerger failed: {java_raw}"
    assert java["pages"] == 6, f"upstream merged page count: {java['pages']}"
    assert java["text"] == expected_text, (
        f"upstream page order divergence:\n"
        f"  expected: {expected_text}\n  PDFBox:   {java['text']}"
    )

    # pypdfbox merge CLI on the SAME three inputs, driven with the SAME argv
    # shape upstream picocli requires: one repeated -i per input (-i a -i b -i c
    # -o out). This is the load-bearing CLI-contract parity claim.
    py_out = tmp_path / "py_merged.pdf"
    argv = ["merge"]
    for src in sources:
        argv += ["-i", str(src)]
    argv += ["-o", str(py_out)]
    rc = cli.run_cli(argv)
    assert rc == 0, f"pypdfbox merge CLI returned {rc}"

    py_pages, py_text = _read_py_merge(py_out)

    # Page count + per-page text, in merged order, vs upstream.
    assert py_pages == java["pages"], (
        f"merged page count: pypdfbox {py_pages} vs PDFBox {java['pages']}"
    )
    assert py_text == java["text"], (
        f"page-order text divergence:\n"
        f"  pypdfbox: {py_text}\n  PDFBox:   {java['text']}"
    )
    assert py_text == expected_text

    # pypdfbox output must be structurally clean.
    py_rc, py_log = _qpdf_check(py_out)
    assert py_rc <= 3, f"pypdfbox merge failed qpdf --check (rc={py_rc}):\n{py_log}"


def test_merge_tool_reloadable_page_count(tmp_path: Path) -> None:
    """Regression pin: the pypdfbox ``merge`` CLI output reloads cleanly and the
    merged page count equals the sum of the input page counts (CLI surface,
    independent of the oracle jar)."""
    sources, expected_text = _build_source_set(tmp_path / "src")
    py_out = tmp_path / "merged.pdf"
    rc = cli.run_cli(
        ["merge", "-i", *[str(s) for s in sources], "-o", str(py_out)]
    )
    assert rc == 0
    py_pages, py_text = _read_py_merge(py_out)
    assert py_pages == 6
    assert py_text == expected_text
