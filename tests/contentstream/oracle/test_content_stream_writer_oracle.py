"""Live PDFBox differential parity for ContentStreamWriter round-trip.

Parses a content stream with pypdfbox's ``PDFStreamParser`` then re-serializes
the token list with ``ContentStreamWriter.write_tokens(list)`` and compares the
resulting raw bytes against Apache PDFBox's ``ContentStreamWriter`` on the same
token list (via the ``ContentStreamWriterProbe`` Java oracle).

This pins the writer's exact byte output: operand spacing (trailing space after
every operand), the ``\\n`` after every operator, the inline-image
``BI``/``ID``/``EI`` framing with the parameter dictionary printed inline (no
``<<>>``) and the raw image bytes copied verbatim, and the COS operand
formatting (float / int / name / string / array / dict).

The probe emits the writer's output as lower-hex (binary-safe — inline-image
data is arbitrary bytes), so we compare ``writer_output.hex()`` against it.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from pypdfbox.pdfparser.pdf_stream_parser import PDFStreamParser
from pypdfbox.pdfwriter.content_stream_writer import ContentStreamWriter
from pypdfbox.pdmodel.pd_document import PDDocument
from tests.oracle.harness import requires_oracle, run_probe_text

_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"

# (relative fixture path, page index) — varied content: text, vector
# graphics, clipping, images, form XObjects, rotated pages, AcroForm.
_CASES = [
    ("text/BidiSample.pdf", 0),
    ("text/input/eu-001.pdf", 0),
    ("multipdf/rot0.pdf", 0),
    ("multipdf/rot90.pdf", 0),
    ("multipdf/PDFBOX-4417-001031.pdf", 0),
    ("pdfwriter/unencrypted.pdf", 0),
    ("pdfwriter/PDFBOX-3110-poems-beads.pdf", 0),
    ("pdmodel/interactive/form/AcroFormsBasicFields.pdf", 0),
    ("pdmodel/interactive/annotation/AnnotationTypes.pdf", 0),
    ("multipdf/PDFA3A.pdf", 0),
]

# Raw content-stream cases — exercise the inline-image (BI/ID/EI) writer path
# (parameter-dictionary inline serialization + verbatim image-byte copy)
# without needing a binary PDF fixture.
_RAW_CASES = [
    "contentstream/inline_image_basic.cs",
    "contentstream/inline_image_embedded_ei.cs",
    "contentstream/marked_content_ops.cs",
]


def _serialize(tokens: list[object]) -> str:
    buf = io.BytesIO()
    writer = ContentStreamWriter(buf)
    # List-overload form: no trailing newline, mirrors upstream
    # writeTokens(List<?>) which the probe also uses.
    writer.write_tokens(list(tokens))
    return buf.getvalue().hex()


@requires_oracle
@pytest.mark.parametrize(
    ("rel", "page"),
    _CASES,
    ids=[f"{rel.replace('/', '_')}_p{page}" for rel, page in _CASES],
)
def test_content_stream_writer_matches_pdfbox(rel: str, page: int) -> None:
    fixture = _FIXTURES / rel
    assert fixture.is_file(), f"missing fixture: {fixture}"
    java = run_probe_text("ContentStreamWriterProbe", str(fixture), str(page))
    doc = PDDocument.load(fixture)
    try:
        pd_page = doc.get_page(page)
        tokens = PDFStreamParser(
            pd_page.get_contents_for_stream_parsing()
        ).parse()
        py = _serialize(tokens)
    finally:
        doc.close()
    assert py == java


@requires_oracle
@pytest.mark.parametrize(
    "rel", _RAW_CASES, ids=[r.replace("/", "_") for r in _RAW_CASES]
)
def test_content_stream_writer_raw_matches_pdfbox(rel: str) -> None:
    fixture = _FIXTURES / rel
    assert fixture.is_file(), f"missing fixture: {fixture}"
    java = run_probe_text("ContentStreamWriterProbe", str(fixture), "--raw")
    tokens = PDFStreamParser.from_bytes(fixture.read_bytes()).parse()
    py = _serialize(tokens)
    assert py == java
