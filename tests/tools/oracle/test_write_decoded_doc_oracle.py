"""Live Apache PDFBox parity for the ``WriteDecodedDoc`` CLI tool.

pypdfbox builds a one-page PDF whose content stream is ``/FlateDecode``
compressed, then:

* drives Apache PDFBox 3.0.7's ``org.apache.pdfbox.tools.WriteDecodedDoc`` CLI
  on that input via the ``WriteDecodedDocProbe`` Java probe, which reloads the
  produced "decoded" output and emits its structural shape as JSON
  (``exitCode``/``pages``/``anyStreamHasFilter``/``streamCount``/``text``); and
* runs pypdfbox's own ``WriteDecodedDoc`` tool on the *same* compressed input.

The parity claim: both tools decode every stream in place and drop its
``/Filter`` entry, so the reloaded output carries NO ``/Filter`` on any stream
object (``anyStreamHasFilter == False``), preserves the page count, and
preserves the extracted text. pypdfbox's output is additionally run through
``qpdf --check`` to prove the produced file is structurally clean.

This is the end-to-end WriteDecodedDoc surface: compress -> upstream-decode and
compress -> pypdfbox-decode must converge on the same uncompressed document.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from pypdfbox.cos import COSStream
from pypdfbox.cos.cos_name import COSName
from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.text.pdf_text_stripper import PDFTextStripper
from pypdfbox.tools.write_decoded_doc import WriteDecodedDoc
from tests.oracle.harness import requires_oracle, run_probe_text

# Content stream whose extracted text is stable across both engines.
_CONTENT = b"BT /F1 12 Tf 50 700 Td (WriteDecodedDoc parity sample) Tj ET"
_EXPECTED_TEXT = "WriteDecodedDoc parity sample"


def _escape(value: str) -> str:
    """Mirror the Java probe's JSON string escaping for direct comparison."""
    out: list[str] = []
    for ch in value:
        if ch == "\\":
            out.append("\\\\")
        elif ch == '"':
            out.append('\\"')
        elif ch == "\n":
            out.append("\\n")
        elif ch == "\r":
            out.append("\\r")
        elif ch == "\t":
            out.append("\\t")
        elif ord(ch) < 0x20:
            out.append(f"\\u{ord(ch):04x}")
        else:
            out.append(ch)
    return "".join(out)


def _build_flate_pdf(path: Path) -> Path:
    """Write a one-page PDF whose content stream is FlateDecode-compressed."""
    doc = PDDocument()
    try:
        page = PDPage()
        doc.add_page(page)
        stream = COSStream()
        with stream.create_output_stream(COSName.FLATE_DECODE) as out:
            out.write(_CONTENT)
        # Sanity: the fixture really is filter-bearing before decoding.
        assert stream.get_item(COSName.FILTER) == COSName.FLATE_DECODE
        page.set_contents(stream)
        doc.save(path)
    finally:
        doc.close()
    return path


def _qpdf_check(path: Path) -> None:
    """Assert ``qpdf --check`` reports a clean file (skip if qpdf absent)."""
    qpdf = shutil.which("qpdf")
    if qpdf is None:  # pragma: no cover - environment dependent
        pytest.skip("qpdf not installed")
    result = subprocess.run(
        [qpdf, "--check", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    # qpdf returns 0 (clean) or 3 (warnings only); 2 = errors. Reject errors.
    assert result.returncode in (0, 3), (
        f"qpdf --check failed for {path}:\n{result.stdout}\n{result.stderr}"
    )


def _pypdfbox_summary(out_path: Path) -> tuple[bool, int, int, str]:
    """Reload a pypdfbox-decoded file; return its probe-shaped fields."""
    with PDDocument.load(out_path) as doc:
        pages = doc.get_number_of_pages()
        cos_doc = doc.get_document()
        stream_count = 0
        any_filter = False
        for cos_obj in cos_doc.get_objects():
            base = cos_obj.get_object()
            if isinstance(base, COSStream):
                stream_count += 1
                if base.get_item(COSName.FILTER) is not None:
                    any_filter = True
        text = PDFTextStripper().get_text(doc)
    return any_filter, pages, stream_count, text


@requires_oracle
def test_write_decoded_doc_matches_pdfbox(tmp_path: Path) -> None:
    src = _build_flate_pdf(tmp_path / "compressed.pdf")

    # Upstream WriteDecodedDoc CLI on the Flate-compressed input.
    java_out = tmp_path / "java_decoded.pdf"
    java_raw = run_probe_text(
        "WriteDecodedDocProbe", str(src), str(java_out)
    )
    java = json.loads(java_raw)

    # Sanity: upstream succeeded and produced a filter-free file.
    assert java["exitCode"] == 0, f"upstream WriteDecodedDoc failed: {java_raw}"
    assert java["pages"] == 1
    assert java["anyStreamHasFilter"] is False
    assert _EXPECTED_TEXT in java["text"]

    # pypdfbox WriteDecodedDoc on the SAME compressed input.
    py_out = tmp_path / "py_decoded.pdf"
    rc = WriteDecodedDoc.main([str(src), str(py_out)])
    assert rc == 0

    any_filter, pages, stream_count, text = _pypdfbox_summary(py_out)

    # Structural parity against upstream's decoded output.
    assert any_filter == java["anyStreamHasFilter"]
    assert pages == java["pages"]
    assert text == java["text"], (
        "WriteDecodedDoc text divergence:\n"
        f"  java: {java['text']!r}\n"
        f"  py:   {text!r}"
    )
    # The whole point of the tool: no stream keeps a /Filter after decoding.
    assert any_filter is False
    assert stream_count >= 1

    # pypdfbox's output must be structurally clean.
    _qpdf_check(py_out)


@requires_oracle
def test_write_decoded_doc_output_reloads_without_filter(tmp_path: Path) -> None:
    """Regression pin: the pypdfbox-decoded file reloads with the same page
    count and text, and no stream object carries a /Filter, matching the
    upstream WriteDecodedDoc contract."""
    src = _build_flate_pdf(tmp_path / "comp.pdf")
    py_out = tmp_path / "dec.pdf"
    rc = WriteDecodedDoc.main([str(src), str(py_out)])
    assert rc == 0
    any_filter, pages, stream_count, text = _pypdfbox_summary(py_out)
    assert pages == 1
    assert any_filter is False
    assert stream_count >= 1
    assert _EXPECTED_TEXT in text
