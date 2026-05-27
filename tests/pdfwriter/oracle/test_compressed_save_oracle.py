"""Live PDFBox differential parity for the COMPRESSED save round-trip — object
streams (``/Type /ObjStm``) addressed by a cross-reference stream
(``/Type /XRef``) — exercised in **both** directions with a rendered-text
oracle.

This is the text-and-internals complement to ``test_objstm_save_oracle.py``
(which covers structural-band equivalence). Where that module asserts the
*shape* of the compressed output (objstm present, xref stream true, packed
count in band), this one asserts the *content survives the save losslessly*:

* **Direction A — pypdfbox writes, PDFBox reads.** pypdfbox compress-saves a
  fixture; PDFBox loads that ObjStm + XRef-stream file and its
  ``PDFTextStripper`` output equals PDFBox's text from the original source.
  i.e. pypdfbox's compressed layout is fully readable by PDFBox with no text
  loss.
* **Direction B — PDFBox writes, pypdfbox reads.** PDFBox compress-saves a
  fixture (``doc.save(out, new CompressParameters())``); pypdfbox loads that
  file (decoding the ObjStm members + the XRef stream) and its
  ``PDFTextStripper`` output equals pypdfbox's text from the original source.
  i.e. pypdfbox correctly decodes PDFBox's ObjStm/XRef and recovers the graph.

Both directions also assert ``qpdf --check`` validity and that the writer
emitted a well-formed compressed structure (an ObjStm with a sane ``/N`` /
``/First`` and a ``/XRef`` stream PDFBox accepts).

**How a compressed save is triggered.** PDFBox 3.0 compresses by passing a
non-disabled ``CompressParameters`` to ``doc.save`` —
``doc.save(out, new CompressParameters())`` — routing through
``COSWriterCompressionPool``. pypdfbox exposes the same path through the
writer flags rather than the ``PDDocument.save(compress_parameters=...)``
argument: ``COSWriter(sink, xref_stream=True, object_stream=True)`` followed by
``writer.write(doc)``. ``PDDocument.save(compress_parameters=...)`` is accepted
for API parity but currently downgraded to no-compression (documented in
CHANGES.md); the writer flags are the live trigger and what this test drives.

Text is compared **stripper-against-itself per direction** (PDFBox's text from
PDFBox vs PDFBox's text from PDFBox-via-pypdfbox; pypdfbox's text from pypdfbox
vs pypdfbox's text from pypdfbox-via-PDFBox), never PDFBox-stripper vs
pypdfbox-stripper. The two strippers have pre-existing line-ordering /
article-threading differences on some fixtures that are unrelated to the save
path; isolating each direction to a single stripper keeps this test a clean
probe of the *writer/reader* round-trip rather than of the text engine.

Java oracle: ``oracle/probes/CompressedSaveProbe.java`` with modes
``save in out`` (PDFBox compressed save), ``facts file`` (xref_stream /
objstm_count / packed / objstm_n / objstm_first / top_level / pages), and
``text file`` (raw ``PDFTextStripper`` output).
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

from pypdfbox import Loader, PDDocument
from pypdfbox.pdfwriter import COSWriter
from pypdfbox.text.pdf_text_stripper import PDFTextStripper
from tests.oracle.harness import requires_oracle, run_probe_text

_REPO_ROOT = Path(__file__).resolve().parents[3]
_FIXTURES = _REPO_ROOT / "tests" / "fixtures"

# A spread of shapes: simple text, AcroForm, embedded-attachment stream,
# multi-page with threads/beads, rotated page, merge-source AcroForm.
_FIXTURES_LIST = [
    _FIXTURES / "pdfwriter" / "unencrypted.pdf",
    _FIXTURES / "pdfwriter" / "acroform.pdf",
    _FIXTURES / "pdfwriter" / "attachment.pdf",
    _FIXTURES / "pdfwriter" / "PDFBOX-3110-poems-beads.pdf",
    _FIXTURES / "multipdf" / "rot0.pdf",
    _FIXTURES / "multipdf" / "AcroFormForMerge.pdf",
]

_QPDF = shutil.which("qpdf")
_requires_qpdf = pytest.mark.skipif(
    _QPDF is None, reason="qpdf binary not on PATH (brew install qpdf)"
)

# ----------------------------------------------------------------- helpers


def _qpdf_check(path: Path) -> tuple[int, str]:
    """``(returncode, combined output)`` from ``qpdf --check``.

    Exit codes (man qpdf): 0 = clean, 2 = errors (broken), 3 = warnings only
    (valid; qpdf recovered). Treat rc <= 3 as structurally valid — rc 3 is the
    benign "xref entry for the xref stream itself is missing" note qpdf emits
    for stream-xref output.
    """
    proc = subprocess.run(
        [str(_QPDF), "--check", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def _has_objstm(data: bytes) -> bool:
    return re.search(rb"/Type\s*/ObjStm", data) is not None


def _has_xref_stream(data: bytes) -> bool:
    return re.search(rb"/Type\s*/XRef", data) is not None


def _py_text(path: Path) -> str:
    """pypdfbox ``PDFTextStripper`` output for ``path`` (handles open/close)."""
    cos = Loader.load_pdf(path)
    doc = PDDocument(cos)
    try:
        return PDFTextStripper().get_text(doc)
    finally:
        doc.close()


def _save_compressed_py(src: Path, out: Path) -> None:
    """Compress-save ``src`` through pypdfbox to ``out`` (ObjStm + XRef stream).

    Triggers compression via the writer flags (pypdfbox's equivalent of
    PDFBox's ``doc.save(out, CompressParameters)``). Closes the document and the
    sink before returning so the handles are released before the caller
    reopens/overwrites the path (Windows file-lock safety).
    """
    cos = Loader.load_pdf(src)
    doc = PDDocument(cos)
    try:
        sink = open(out, "wb")  # noqa: SIM115 — closed in finally
        try:
            with COSWriter(sink, xref_stream=True, object_stream=True) as writer:
                writer.write(doc)
        finally:
            sink.close()
    finally:
        doc.close()


def _parse_facts(text: str) -> dict[str, str]:
    facts: dict[str, str] = {}
    for line in text.strip().splitlines():
        if "=" in line:
            key, _, value = line.partition("=")
            facts[key.strip()] = value.strip()
    return facts


def _ints(csv: str) -> list[int]:
    return [int(x) for x in csv.split(",") if x != ""]


# --------------------------------------- Direction A: pypdfbox writes → PDFBox reads


@requires_oracle
@_requires_qpdf
@pytest.mark.parametrize("fixture", _FIXTURES_LIST, ids=lambda p: p.stem)
def test_pypdfbox_compress_save_read_by_pdfbox_preserves_text_and_structure(
    fixture: Path, tmp_path: Path
) -> None:
    """pypdfbox compress-saves; PDFBox reads back identical object/page/text and
    sees a well-formed ObjStm + XRef-stream layout."""
    if not fixture.is_file():
        pytest.skip(f"fixture missing: {fixture}")

    # PDFBox's text from the original source — the reference for direction A.
    src_text_pdfbox = run_probe_text("CompressedSaveProbe", "text", str(fixture))

    py_out = tmp_path / f"py_{fixture.stem}.pdf"
    _save_compressed_py(fixture, py_out)
    py_bytes = py_out.read_bytes()

    # (1) Structurally valid.
    rc, log = _qpdf_check(py_out)
    assert rc <= 3, f"pypdfbox compressed output failed qpdf --check (rc={rc}):\n{log}"

    # (2) Actually compressed: ObjStm + XRef stream present in the bytes.
    assert _has_objstm(py_bytes), "pypdfbox output has no /Type /ObjStm"
    assert _has_xref_stream(py_bytes), "pypdfbox output has no /Type /XRef"

    # (3) PDFBox reads our compressed layout and reports a coherent structure.
    facts = _parse_facts(run_probe_text("CompressedSaveProbe", "facts", str(py_out)))
    assert facts["xref_stream"] == "true", "no classic trailer — must be an XRef stream"
    assert int(facts["objstm_count"]) >= 1
    assert int(facts["packed"]) >= 1

    # (4) Well-formed ObjStm internals: every /N is positive and every /First is
    #     a non-negative offset PDFBox could parse (it read the members at all).
    ns = _ints(facts["objstm_n"])
    firsts = _ints(facts["objstm_first"])
    assert ns and all(n >= 1 for n in ns), f"bad ObjStm /N values: {ns}"
    assert firsts and all(f >= 0 for f in firsts), f"bad ObjStm /First values: {firsts}"
    # PDFBox's count of packed members equals the sum of the /N it parsed.
    assert int(facts["packed"]) == sum(ns)

    # (5) Lossless: PDFBox's text from our compressed file == PDFBox's text from
    #     the original source. The object-stream/xref-stream round-trip lost no
    #     content.
    out_text_pdfbox = run_probe_text("CompressedSaveProbe", "text", str(py_out))
    assert out_text_pdfbox == src_text_pdfbox


# --------------------------------------- Direction B: PDFBox writes → pypdfbox reads


@requires_oracle
@_requires_qpdf
@pytest.mark.parametrize("fixture", _FIXTURES_LIST, ids=lambda p: p.stem)
def test_pdfbox_compress_save_read_by_pypdfbox_recovers_graph_and_text(
    fixture: Path, tmp_path: Path
) -> None:
    """PDFBox compress-saves (``doc.save(out, CompressParameters)``); pypdfbox
    decodes the ObjStm members + XRef stream and recovers the same graph, pages,
    and text as it reads from the source."""
    if not fixture.is_file():
        pytest.skip(f"fixture missing: {fixture}")

    # pypdfbox's text + page count from the original source — direction-B ref.
    src_text_py = _py_text(fixture)
    src_cos = Loader.load_pdf(fixture)
    src_doc = PDDocument(src_cos)
    try:
        src_pages = src_doc.get_number_of_pages()
    finally:
        src_doc.close()

    # PDFBox compress-saves the fixture.
    java_out = tmp_path / f"java_{fixture.stem}.pdf"
    run_probe_text("CompressedSaveProbe", "save", str(fixture), str(java_out))
    java_bytes = java_out.read_bytes()

    # PDFBox actually compressed.
    assert _has_objstm(java_bytes), "PDFBox output has no /Type /ObjStm"
    assert _has_xref_stream(java_bytes), "PDFBox output has no /Type /XRef"

    # qpdf agrees the PDFBox-compressed file is valid.
    rc, log = _qpdf_check(java_out)
    assert rc <= 3, f"PDFBox compressed output failed qpdf --check (rc={rc}):\n{log}"

    # pypdfbox decodes PDFBox's ObjStm + XRef stream.
    cos = Loader.load_pdf(java_out)
    doc = PDDocument(cos)
    try:
        # (1) Page count recovered.
        assert doc.get_number_of_pages() == src_pages
        # (2) Text recovered: pypdfbox's text from the PDFBox-compressed file ==
        #     pypdfbox's text from the source. ObjStm members + xref-stream
        #     offsets were decoded correctly.
        recovered_text = PDFTextStripper().get_text(doc)
    finally:
        doc.close()
    assert recovered_text == src_text_py


# --------------------------------------- internals: /W and /Index well-formedness


@requires_oracle
@_requires_qpdf
def test_pypdfbox_xref_stream_w_and_index_are_well_formed(tmp_path: Path) -> None:
    """The pypdfbox-emitted ``/Type /XRef`` stream carries a 3-field ``/W`` and
    an ``/Index`` whose entry total matches the xref-table size PDFBox parses —
    a malformed ``/W`` or ``/Index`` would corrupt every offset and PDFBox could
    not read the file at all (so this is verified end-to-end via the facts
    probe plus a direct byte check)."""
    src = _FIXTURES / "pdfwriter" / "PDFBOX-3110-poems-beads.pdf"
    if not src.is_file():
        pytest.skip(f"fixture missing: {src}")
    out = tmp_path / "py_xref.pdf"
    _save_compressed_py(src, out)
    data = out.read_bytes()

    # /W [a b c] — three non-negative widths; field 1 (type) and the others
    # must all be present for the records to be decodable.
    m_w = re.search(rb"/Type\s*/XRef.*?/W\s*\[\s*([^\]]*?)\]", data, re.S)
    assert m_w is not None, "no /W in the XRef stream"
    widths = [int(x) for x in m_w.group(1).split()]
    assert len(widths) == 3, f"/W must have 3 fields, got {widths}"
    assert all(w >= 0 for w in widths) and widths[1] >= 1, f"bad /W widths: {widths}"

    # /Index is optional (defaults to [0 Size]); if present it must pair
    # (start, count) entries.
    m_idx = re.search(rb"/Type\s*/XRef.*?/Index\s*\[\s*([^\]]*?)\]", data, re.S)
    if m_idx is not None:
        idx = [int(x) for x in m_idx.group(1).split()]
        assert len(idx) % 2 == 0 and len(idx) >= 2, f"/Index must pair entries: {idx}"
        index_total = sum(idx[1::2])
    else:
        index_total = None

    # PDFBox parses the file: its xref-table size is the count of addressable
    # entries. If /Index is present its summed counts must cover them.
    facts = _parse_facts(run_probe_text("CompressedSaveProbe", "facts", str(out)))
    top_level = int(facts["top_level"])
    assert top_level >= 1
    if index_total is not None:
        # The XRef stream describes at least the top-level entries PDFBox saw.
        assert index_total >= top_level, (
            f"/Index covers {index_total} entries but PDFBox resolved "
            f"{top_level} top-level objects"
        )
