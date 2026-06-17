"""Live Apache PDFBox parity for the ``ExtractXMP`` CLI tool
(``org.apache.pdfbox.tools.ExtractXMP`` vs pypdfbox's
``pypdfbox.tools.extract_xmp.ExtractXMP``).

ExtractXMP pulls the XMP metadata packet out of a PDF (document-level by
default, or a single page via ``-page N``) and, with ``-console``, writes the
exact packet bytes to stdout. The parity surface:

* **document XMP present** → both tools emit the identical packet bytes and
  exit 0;
* **no XMP metadata** → both write "No XMP metadata available" to stderr and
  exit 1 (the probe reports exit 1 + empty stdout);
* **page out of range** → both write "Page N doesn't exist" to stderr and
  exit 1.

The harness drives the real upstream CLI (as an actual subprocess — upstream
``ExtractXMP`` exposes only ``main`` which calls ``System.exit``) through
``ExtractXmpToolProbe``, which Base64-encodes the captured stdout so binary
packets survive the JSON channel. pypdfbox's CLI is driven over the same input
and its console bytes captured for a byte-for-byte comparison.
"""

from __future__ import annotations

import base64
import contextlib
import io
import json
import sys
from pathlib import Path

from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.pdmodel.common import PDMetadata, PDRectangle
from pypdfbox.tools.extract_xmp import ExtractXMP
from tests.oracle.harness import requires_oracle, run_probe_text

_XMP = (
    b'<?xpacket begin="" id="W5M0MpCehiHzreSzNTczkc9d"?>'
    b'<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF '
    b'xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
    b'<rdf:Description xmlns:dc="http://purl.org/dc/elements/1.1/">'
    b"<dc:title>HELLO</dc:title></rdf:Description></rdf:RDF>"
    b'</x:xmpmeta><?xpacket end="w"?>'
)


def _build_with_xmp(path: Path) -> None:
    doc = PDDocument()
    try:
        doc.add_page(PDPage(PDRectangle.LETTER))
        meta = PDMetadata(doc)
        meta.import_xmp_metadata(_XMP)
        doc.get_document_catalog().set_metadata(meta)
        doc.save(str(path))
    finally:
        doc.close()


def _build_without_xmp(path: Path) -> None:
    doc = PDDocument()
    try:
        doc.add_page(PDPage(PDRectangle.LETTER))
        doc.save(str(path))
    finally:
        doc.close()


def _py_console(infile: Path, *args: str) -> tuple[int, bytes]:
    """Drive pypdfbox's ExtractXMP CLI in -console mode; return (exit, stdout)."""
    buf = io.BytesIO()

    class _BytesStdout:
        def __init__(self) -> None:
            self.buffer = buf

        def write(self, _s):  # noqa: ANN001 — text passthrough not used here
            pass

        def flush(self) -> None:
            pass

    real = sys.stdout
    sys.stdout = _BytesStdout()
    try:
        rc = ExtractXMP.main(["-i", str(infile), "-console", *args])
    finally:
        sys.stdout = real
    return rc, buf.getvalue()


@requires_oracle
def test_extract_xmp_document_bytes_match_pdfbox(tmp_path: Path) -> None:
    """Document-level XMP: upstream and pypdfbox emit byte-identical packets and
    both exit 0."""
    src = tmp_path / "has_xmp.pdf"
    _build_with_xmp(src)

    java = json.loads(run_probe_text("ExtractXmpToolProbe", str(src)))
    assert java["exitCode"] == 0, f"upstream ExtractXMP failed: {java}"
    java_bytes = base64.b64decode(java["xmpBase64"])

    py_rc, py_bytes = _py_console(src)
    assert py_rc == 0
    assert py_bytes == java_bytes, (
        "XMP packet byte divergence:\n"
        f"  pypdfbox: {py_bytes!r}\n  PDFBox:   {java_bytes!r}"
    )
    # Sanity: the packet round-trips the title we embedded.
    assert b"HELLO" in py_bytes


@requires_oracle
def test_extract_xmp_no_metadata_matches_pdfbox(tmp_path: Path) -> None:
    """No XMP: both tools exit 1 with empty stdout."""
    src = tmp_path / "no_xmp.pdf"
    _build_without_xmp(src)

    java = json.loads(run_probe_text("ExtractXmpToolProbe", str(src)))
    assert java["exitCode"] == 1, f"upstream did not signal missing XMP: {java}"
    assert base64.b64decode(java["xmpBase64"]) == b""

    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        py_rc, py_bytes = _py_console(src)
    assert py_rc == 1
    assert py_bytes == b""
    assert "No XMP metadata available" in err.getvalue()


@requires_oracle
def test_extract_xmp_page_out_of_range_matches_pdfbox(tmp_path: Path) -> None:
    """``-page N`` past the end: both tools exit 1 with empty stdout."""
    src = tmp_path / "has_xmp.pdf"
    _build_with_xmp(src)

    java = json.loads(
        run_probe_text("ExtractXmpToolProbe", str(src), "-page", "99")
    )
    assert java["exitCode"] == 1
    assert base64.b64decode(java["xmpBase64"]) == b""

    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        py_rc, py_bytes = _py_console(src, "-page", "99")
    assert py_rc == 1
    assert py_bytes == b""
    assert "Page 99 doesn't exist" in err.getvalue()
