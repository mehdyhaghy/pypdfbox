"""Live PDFBox differential parity for the trailer ``/ID`` *synthesis* path and
cross-readability (``pypdfbox.pdfwriter.cos_writer``).

``FileIdProbe`` / ``test_file_id_oracle`` already cover read / preserve /
incremental on fixtures that *already* carry an ``/ID``. This module targets the
branch those never exercise: a document that **lacks** an ``/ID``.

ISO 32000-1 §14.4 / PDF §7.5.5 — when a producer writes a file with no existing
identifier it synthesises ``/ID`` as a two-element array. PDFBox 3.0.7's
``COSWriter`` feeds (current time + file size + Info-dict entries) into a
``SHA-256`` ``MessageDigest`` and uses the **full, untruncated 32-byte digest**
for *both* halves, so a freshly-synthesised array is ``[id id]`` — two identical
32-byte byte strings (they only diverge once the file is later updated).

Because the digest input is time-based, this is a *structural*-equivalence check
(not byte-equality). What must agree with PDFBox:

1. A document with no ``/ID`` gets a 2-element array of two **32-byte** strings
   on a full save, with both halves **identical** (``id0 == id1``).
2. Cross-readability: PDFBox can parse the ``/ID`` pypdfbox synthesised, and
   pypdfbox can parse the ``/ID`` PDFBox synthesised — same bytes, same shape.
3. Both outputs pass ``qpdf --check``.

The Java oracle is ``FileIdSynthProbe`` (modes ``freshsave`` / ``read``); it
emits line-oriented ``key=value`` facts this module parses.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from pypdfbox import Loader, PDDocument
from pypdfbox.cos import COSArray, COSName, COSString
from pypdfbox.pdmodel import PDPage
from tests.oracle.harness import requires_oracle, run_probe_text

_QPDF = shutil.which("qpdf")
_requires_qpdf = pytest.mark.skipif(
    _QPDF is None, reason="qpdf binary not on PATH (brew install qpdf)"
)

_ID_NAME = COSName.get_pdf_name("ID")


# ----------------------------------------------------------------- helpers


def _qpdf_ok(path: Path) -> tuple[int, str]:
    proc = subprocess.run(
        [str(_QPDF), "--check", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def _parse_probe(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.splitlines():
        if "=" in line:
            k, _, v = line.partition("=")
            out[k] = v
    return out


def _py_id(path: Path) -> tuple[bytes, bytes] | None:
    """Reload ``path`` through pypdfbox and return ``(id0, id1)`` bytes, or
    ``None`` if the trailer lacks a well-formed 2-element ``/ID``."""
    cos = Loader.load_pdf(path)
    try:
        trailer = cos.get_trailer()
        arr = trailer.get_dictionary_object(_ID_NAME) if trailer else None
        if not isinstance(arr, COSArray) or arr.size() != 2:
            return None
        e0 = arr.get_object(0)
        e1 = arr.get_object(1)
        if not isinstance(e0, COSString) or not isinstance(e1, COSString):
            return None
        return e0.get_bytes(), e1.get_bytes()
    finally:
        cos.close()


def _fresh_py_doc_no_id(out: Path) -> None:
    """Save a brand-new one-page pypdfbox document (no source /ID) to ``out``,
    exercising COSWriter's ``/ID`` synthesis path."""
    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        # The in-memory doc must carry no /ID before save (synthesis path).
        trailer = doc.get_document().get_trailer()
        if trailer is not None:
            assert not isinstance(
                trailer.get_dictionary_object(_ID_NAME), COSArray
            ), "fresh PDDocument unexpectedly already has an /ID"
        doc.save(str(out))
    finally:
        doc.close()


# --------------------------------------------------- fresh-synthesis structure


@requires_oracle
@_requires_qpdf
def test_synthesised_id_is_two_identical_32_byte_strings_like_pdfbox(
    tmp_path: Path,
) -> None:
    """A document with no /ID gets a 2-element array of two identical 32-byte
    strings on a full save — matching PDFBox 3.0.7's COSWriter, which uses the
    full SHA-256 digest for both halves of a synthesised identifier."""
    # --- Java oracle: PDFBox synthesises [id id] for a fresh doc ----------
    java_out = tmp_path / "java_fresh.pdf"
    jf = _parse_probe(
        run_probe_text("FileIdSynthProbe", "freshsave", str(java_out))
    )
    assert jf["pre_id_present"] == "false", "fresh PDFBox doc already had an /ID"
    assert jf["id_present"] == "true"
    assert jf["id0_len"] == "32", "PDFBox synthesised half is not 32 bytes"
    assert jf["id1_len"] == "32"
    assert jf["id0_eq_id1"] == "true", "PDFBox synthesised halves are not equal"

    # --- pypdfbox: same structure ---------------------------------------
    py_out = tmp_path / "py_fresh.pdf"
    _fresh_py_doc_no_id(py_out)
    py_ids = _py_id(py_out)
    assert py_ids is not None, "pypdfbox full save synthesised no 2-element /ID"
    e0, e1 = py_ids
    assert len(e0) == 32, f"pypdfbox synthesised /ID[0] is {len(e0)} bytes, want 32"
    assert len(e1) == 32, f"pypdfbox synthesised /ID[1] is {len(e1)} bytes, want 32"
    assert e0 == e1, "pypdfbox synthesised /ID halves are not identical"

    # Validity on both sides.
    j_rc, j_log = _qpdf_ok(java_out)
    p_rc, p_log = _qpdf_ok(py_out)
    assert j_rc <= 3, f"Java fresh /ID save failed qpdf (rc={j_rc}):\n{j_log}"
    assert p_rc <= 3, f"pypdfbox fresh /ID save failed qpdf (rc={p_rc}):\n{p_log}"


# --------------------------------------------------------- cross-readability


@requires_oracle
def test_pdfbox_reads_pypdfbox_synthesised_id(tmp_path: Path) -> None:
    """PDFBox parses the /ID pypdfbox synthesised, seeing the same bytes and
    the same 2-element/32-byte/identical-halves shape (round-trip readability
    in the python->java direction)."""
    py_out = tmp_path / "py_for_java.pdf"
    _fresh_py_doc_no_id(py_out)
    py_ids = _py_id(py_out)
    assert py_ids is not None
    e0, e1 = py_ids

    jf = _parse_probe(run_probe_text("FileIdSynthProbe", "read", str(py_out)))
    assert jf["id_present"] == "true", "PDFBox could not read pypdfbox's /ID"
    assert jf["id0_hex"] == e0.hex().upper()
    assert jf["id1_hex"] == e1.hex().upper()
    assert jf["id0_len"] == "32"
    assert jf["id0_eq_id1"] == "true"


@requires_oracle
def test_pypdfbox_reads_pdfbox_synthesised_id(tmp_path: Path) -> None:
    """pypdfbox parses the /ID PDFBox synthesised on a fresh save, seeing the
    same bytes and shape (round-trip readability in the java->python
    direction)."""
    java_out = tmp_path / "java_for_py.pdf"
    jf = _parse_probe(
        run_probe_text("FileIdSynthProbe", "freshsave", str(java_out))
    )
    assert jf["id_present"] == "true"

    py_ids = _py_id(java_out)
    assert py_ids is not None, "pypdfbox could not read PDFBox's synthesised /ID"
    e0, e1 = py_ids
    assert e0.hex().upper() == jf["id0_hex"]
    assert e1.hex().upper() == jf["id1_hex"]
    assert len(e0) == 32
    assert e0 == e1
