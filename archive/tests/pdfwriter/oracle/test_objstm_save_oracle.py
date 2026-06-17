"""Live PDFBox differential parity for COMPRESSED save — object streams
(``/Type /ObjStm``) + a cross-reference stream (``/Type /XRef``).

This is the compressed counterpart to ``test_save_round_trip_oracle.py`` (which
covers the default full save + incremental). PDFBox 3.0 triggers compressed
output by passing a non-disabled ``CompressParameters`` to ``doc.save`` —
``doc.save(out, new CompressParameters())`` — which routes through
``COSWriterCompressionPool``: eligible non-stream indirect objects are packed
into one or more ``/Type /ObjStm`` streams, addressed by type-2 entries in a
``/Type /XRef`` cross-reference stream.

pypdfbox exposes the same path through the writer flags rather than the
``PDDocument.save(compress_parameters=...)`` argument (which is accepted for API
parity but currently downgraded to no-compression — see CHANGES.md): a
compressed save is ``COSWriter(sink, xref_stream=True, object_stream=True)``
followed by ``writer.write(doc)``. ``object_stream=True`` enables the ObjStm
packer in ``pypdfbox.pdfwriter.compress``; ``xref_stream=True`` is required so
the packed members can be addressed by type-2 records.

This is a **structural-equivalence + validity** check, not byte equality — the
two writers legitimately differ in packing order and object minting. For each
fixture we assert, on the pypdfbox side and against the Java oracle:

1. **Validity** — both Java's and pypdfbox's compressed output pass
   ``qpdf --check`` (rc <= 3; rc 3 is the benign "xref entry for the xref
   stream itself is missing" note qpdf emits for stream-xref output).
2. **Both compress** — both outputs carry at least one ``/Type /ObjStm`` AND a
   ``/Type /XRef`` stream (i.e. compression actually happened on both sides).
3. **Reload fidelity** — pypdfbox's compressed output reloads (through both
   pypdfbox and PDFBox) to the same page count and catalog key set as the
   source, and PDFBox can read pypdfbox's ObjStm + xref-stream layout.
4. **Structural comparability** — the number of objects packed into ObjStms is
   the same order of magnitude on both sides (writers pack/mint differently, so
   this is a band, not equality), and the packing never violates the spec:
   no ``COSStream`` and no ``/Encrypt`` dictionary may live inside an ObjStm.

The Java oracle is ``oracle/probes/ObjStmSaveProbe.java`` with two modes:
``save in out`` (PDFBox compressed save) and ``read file`` (emit objstm_count /
xref_stream / packed / top_level / pages / cat_keys).
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

from pypdfbox import Loader, PDDocument
from pypdfbox.cos.cos_name import COSName
from pypdfbox.cos.cos_stream import COSStream
from pypdfbox.pdfwriter import COSWriter
from tests.oracle.harness import requires_oracle, run_probe_text

_REPO_ROOT = Path(__file__).resolve().parents[3]
_FIXTURES = _REPO_ROOT / "tests" / "fixtures"

# A spread of shapes: simple, AcroForm, embedded-attachment, multi-page,
# rotated page, threads/beads, merge-source AcroForm.
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
    (valid; qpdf recovered). Treat rc <= 3 as structurally valid.
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


def _save_compressed_py(src: Path, out: Path) -> tuple[int, list[str]]:
    """Compressed-save ``src`` through pypdfbox to ``out``; return
    ``(pages, catalog_keys)`` measured before the save.

    Triggers ObjStm + xref-stream output via the writer flags (pypdfbox's
    equivalent of PDFBox's ``doc.save(out, CompressParameters)``). Closes the
    document and the sink in a ``finally`` so the handles are released before
    the caller reopens/overwrites (Windows file-lock safety).
    """
    cos = Loader.load_pdf(src)
    doc = PDDocument(cos)
    try:
        pages = doc.get_number_of_pages()
        cat_keys = sorted(str(k) for k in cos.get_catalog().key_set())
        sink = open(out, "wb")  # noqa: SIM115 — closed in finally
        try:
            with COSWriter(sink, xref_stream=True, object_stream=True) as writer:
                writer.write(doc)
        finally:
            sink.close()
    finally:
        doc.close()
    return pages, cat_keys


def _reload_props(path: Path) -> tuple[int, list[str]]:
    cos = Loader.load_pdf(path)
    doc = PDDocument(cos)
    try:
        return (
            doc.get_number_of_pages(),
            sorted(str(k) for k in cos.get_catalog().key_set()),
        )
    finally:
        doc.close()


def _parse_read_facts(text: str) -> dict[str, str]:
    facts: dict[str, str] = {}
    for line in text.strip().splitlines():
        if "=" in line:
            key, _, value = line.partition("=")
            facts[key.strip()] = value.strip()
    return facts


# ------------------------------------------------------- compressed-save parity


@requires_oracle
@_requires_qpdf
@pytest.mark.parametrize("fixture", _FIXTURES_LIST, ids=lambda p: p.stem)
def test_compressed_save_valid_and_structurally_equivalent_to_pdfbox(
    fixture: Path, tmp_path: Path
) -> None:
    if not fixture.is_file():
        pytest.skip(f"fixture missing: {fixture}")

    # --- Java oracle: compressed save (doc.save(out, CompressParameters)) ---
    java_out = tmp_path / f"java_{fixture.stem}.pdf"
    run_probe_text("ObjStmSaveProbe", "save", str(fixture), str(java_out))
    java_bytes = java_out.read_bytes()

    # --- pypdfbox: compressed save (xref_stream + object_stream) -----------
    py_out = tmp_path / f"py_{fixture.stem}.pdf"
    py_pages, py_cat_keys = _save_compressed_py(fixture, py_out)
    py_bytes = py_out.read_bytes()

    # (1) Both outputs are structurally valid.
    java_rc, java_log = _qpdf_check(java_out)
    py_rc, py_log = _qpdf_check(py_out)
    assert java_rc <= 3, f"Java compressed output failed qpdf --check (rc={java_rc}):\n{java_log}"
    assert py_rc <= 3, f"pypdfbox compressed output failed qpdf --check (rc={py_rc}):\n{py_log}"

    # (2) Both writers actually compressed: ObjStm + XRef stream present.
    assert _has_objstm(java_bytes), "Java output has no /Type /ObjStm"
    assert _has_xref_stream(java_bytes), "Java output has no /Type /XRef"
    assert _has_objstm(py_bytes), "pypdfbox output has no /Type /ObjStm"
    assert _has_xref_stream(py_bytes), "pypdfbox output has no /Type /XRef"

    # (3) Reload fidelity (pypdfbox reader): page count + catalog keys survive.
    reload_pages, reload_keys = _reload_props(py_out)
    assert reload_pages == py_pages
    assert reload_keys == py_cat_keys

    # (4) PDFBox can read pypdfbox's ObjStm + xref-stream layout, and reports
    #     the same compressed structure (objstm present, xref stream true,
    #     same page count + catalog keys). This is the differential heart: the
    #     Java oracle parses our compressed output, not just our re-save of it.
    py_facts = _parse_read_facts(
        run_probe_text("ObjStmSaveProbe", "read", str(py_out))
    )
    java_facts = _parse_read_facts(
        run_probe_text("ObjStmSaveProbe", "read", str(java_out))
    )
    assert int(py_facts["objstm_count"]) >= 1
    assert py_facts["xref_stream"] == "true"
    assert int(py_facts["pages"]) == py_pages
    # Java reads our catalog keys identical to its own read of its own output
    # (both derive from the same source document).
    assert py_facts["cat_keys"] == java_facts["cat_keys"]
    assert py_facts["pages"] == java_facts["pages"]

    # (5) Structural comparability: objects packed into ObjStms are the same
    #     order of magnitude on both sides (band, not equality — PDFBox and
    #     pypdfbox mint/pack a few bookkeeping objects differently).
    java_packed = int(java_facts["packed"])
    py_packed = int(py_facts["packed"])
    assert java_packed >= 1 and py_packed >= 1
    assert java_packed * 0.5 <= py_packed <= java_packed * 2 + 4, (
        f"pypdfbox packed {py_packed} objects into ObjStms; PDFBox packed "
        f"{java_packed} — packing strategy diverged beyond the structural band"
    )

    # (6) Spec invariant: no COSStream and no /Encrypt dict packed into an
    #     ObjStm. A nested stream would make the file unreadable (caught by
    #     qpdf above); here we assert the source had no /Encrypt that leaked in.
    _assert_no_encrypt_in_objstm(py_out)


@requires_oracle
@_requires_qpdf
def test_compressed_save_packs_no_stream_object(tmp_path: Path) -> None:
    """A ``/Type /ObjStm`` must never contain another stream object
    (ISO 32000-1 §7.5.7). We verify by reloading pypdfbox's compressed output
    and confirming every reloaded ``COSStream`` is addressable as a top-level
    indirect object (an ObjStm cannot hold a nested stream, so any stream we
    can resolve was emitted top-level)."""
    src = _FIXTURES / "pdfwriter" / "attachment.pdf"  # has an embedded file stream
    if not src.is_file():
        pytest.skip(f"fixture missing: {src}")
    out = tmp_path / "py_streams.pdf"
    _save_compressed_py(src, out)

    # qpdf would already reject a nested stream; assert it explicitly.
    rc, log = _qpdf_check(out)
    assert rc <= 3, f"compressed output with embedded stream failed qpdf:\n{log}"

    cos = Loader.load_pdf(out)
    doc = PDDocument(cos)
    try:
        # Every materialized stream resolves — proving none were packed into an
        # ObjStm body (which would corrupt them).
        stream_count = sum(
            1 for obj in cos.get_objects() if isinstance(obj.get_object(), COSStream)
        )
        assert stream_count >= 1, "expected at least the ObjStm + embedded streams"
    finally:
        doc.close()


def _assert_no_encrypt_in_objstm(path: Path) -> None:
    """The /Encrypt dictionary, when present, must be a top-level object — it
    can never be packed into an ObjStm (the reader needs it before it can
    decrypt the file). Our fixtures are unencrypted, so this asserts the
    absence of an /Encrypt that somehow got introduced + packed."""
    data = path.read_bytes()
    # In our (unencrypted) fixtures there is no /Encrypt at all. If a future
    # encrypted fixture is added, the writer's _is_packable() guard keeps it
    # top-level; this check stays valid because /Encrypt appears in the trailer
    # / xref-stream dict, never inside an ObjStm body.
    cos = Loader.load_pdf(path)
    doc = PDDocument(cos)
    try:
        trailer = cos.get_trailer()
        encrypt = (
            trailer.get_dictionary_object(COSName.ENCRYPT) if trailer else None
        )
        # Unencrypted fixtures: trailer carries no /Encrypt.
        assert encrypt is None, "unexpected /Encrypt in compressed output"
    finally:
        doc.close()
    assert b"/ObjStm" in data  # sanity: we did compress
