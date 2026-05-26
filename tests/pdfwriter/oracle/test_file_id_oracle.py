"""Live PDFBox differential parity for the trailer ``/ID`` file identifier
(``pypdfbox.pdfwriter.cos_writer``).

ISO 32000-1 §14.4 defines ``/ID`` as a two-element array of byte strings: the
first is the *permanent* file identifier (stable for the life of the file), the
second is the *changing* identifier (regenerated whenever the file is updated so
consumers can detect a modification). PDFBox 3.0.7 implements this as:

* **Full save** — preserves an existing ``/ID`` array verbatim; synthesises a
  fresh ``[id id]`` (both halves identical) for a document that lacks one.
* **Incremental save** — preserves ``/ID[0]`` and regenerates ``/ID[1]`` as a
  fresh 32-byte SHA-256 digest over the document state.

This is a *structural*-equivalence check, not byte-equality: the digest input is
time/random based, so the exact bytes differ between the two libraries (and
between runs). What MUST agree is the contract:

1. A fresh full save writes a 2-element ``/ID`` of two 16-byte strings.
2. On incremental save, ``/ID[0]`` is preserved from the source and ``/ID[1]``
   is updated (changed) — verified on both PDFBox and pypdfbox outputs.
3. A document that already carries an ``/ID`` keeps ``/ID[0]`` stable across a
   pypdfbox re-save.
4. Both outputs pass ``qpdf --check``.

The Java oracle is ``FileIdProbe`` (modes: ``read`` / ``save`` /
``incremental``); it emits line-oriented ``key=value`` facts that this module
parses.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from pypdfbox import Loader, PDDocument
from pypdfbox.cos import COSArray, COSName, COSString
from tests.oracle.harness import requires_oracle, run_probe_text

_REPO_ROOT = Path(__file__).resolve().parents[3]
_FIXTURES = _REPO_ROOT / "tests" / "fixtures"

_FIXTURES_LIST = [
    _FIXTURES / "pdfwriter" / "unencrypted.pdf",
    _FIXTURES / "pdfwriter" / "acroform.pdf",
    _FIXTURES / "pdfwriter" / "attachment.pdf",
    _FIXTURES / "multipdf" / "rot0.pdf",
]

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
    ``None`` if the trailer lacks a well-formed 2-element ``/ID``.

    Closes the document in a ``finally`` so the source handle is released
    before the caller reopens/overwrites (Windows file-lock safety).
    """
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


def _save_full_py(src: Path, out: Path) -> None:
    cos = Loader.load_pdf(src)
    doc = PDDocument(cos)
    try:
        doc.save(str(out))
    finally:
        doc.close()


def _save_incremental_py(src: Path, out: Path) -> None:
    cos = Loader.load_pdf(src)
    doc = PDDocument(cos)
    try:
        cos.get_catalog().set_needs_to_be_updated(True)
        doc.save_incremental(str(out))
    finally:
        doc.close()


# ------------------------------------------------------------- fresh full save


@requires_oracle
@_requires_qpdf
@pytest.mark.parametrize("fixture", _FIXTURES_LIST, ids=lambda p: p.stem)
def test_full_save_writes_two_element_16_byte_id_like_pdfbox(
    fixture: Path, tmp_path: Path
) -> None:
    """Both PDFBox and pypdfbox emit a 2-element /ID of two 16-byte strings on
    a full save, and the output is qpdf-valid. (Existing /ID arrays in these
    fixtures are 16-byte, so the preserved array also satisfies the shape.)"""
    if not fixture.is_file():
        pytest.skip(f"fixture missing: {fixture}")

    # --- Java oracle ----------------------------------------------------
    java_out = tmp_path / f"java_{fixture.stem}.pdf"
    java_facts = _parse_probe(
        run_probe_text("FileIdProbe", "save", str(fixture), str(java_out))
    )
    assert java_facts.get("id_present") == "true"
    assert java_facts["id0_len"] == "16"
    assert java_facts["id1_len"] == "16"

    # --- pypdfbox -------------------------------------------------------
    py_out = tmp_path / f"py_{fixture.stem}.pdf"
    _save_full_py(fixture, py_out)
    py_ids = _py_id(py_out)
    assert py_ids is not None, "pypdfbox full save wrote no 2-element /ID"
    e0, e1 = py_ids
    assert len(e0) == 16, f"/ID[0] is {len(e0)} bytes, expected 16"
    assert len(e1) == 16, f"/ID[1] is {len(e1)} bytes, expected 16"

    # Validity on both sides.
    j_rc, j_log = _qpdf_ok(java_out)
    p_rc, p_log = _qpdf_ok(py_out)
    assert j_rc <= 3, f"Java /ID save failed qpdf (rc={j_rc}):\n{j_log}"
    assert p_rc <= 3, f"pypdfbox /ID save failed qpdf (rc={p_rc}):\n{p_log}"


@requires_oracle
@_requires_qpdf
@pytest.mark.parametrize("fixture", _FIXTURES_LIST, ids=lambda p: p.stem)
def test_full_save_preserves_id0_for_doc_with_existing_id(
    fixture: Path, tmp_path: Path
) -> None:
    """A document that already carries an /ID keeps /ID[0] stable across a
    pypdfbox re-save — matching PDFBox, which preserves the array verbatim."""
    if not fixture.is_file():
        pytest.skip(f"fixture missing: {fixture}")

    src_ids = _py_id(fixture)
    assert src_ids is not None, "fixture lacks a 2-element /ID — pick another"
    src_id0, _src_id1 = src_ids

    py_out = tmp_path / f"py_preserve_{fixture.stem}.pdf"
    _save_full_py(fixture, py_out)
    py_ids = _py_id(py_out)
    assert py_ids is not None
    re_id0, _re_id1 = py_ids
    assert re_id0 == src_id0, "pypdfbox full save changed the permanent /ID[0]"

    # PDFBox preserves the whole array on a full save; cross-check /ID[0].
    java_facts = _parse_probe(run_probe_text("FileIdProbe", "read", str(fixture)))
    assert java_facts["id0_hex"] == src_id0.hex().upper()


# ------------------------------------------------------------ incremental save


@requires_oracle
@_requires_qpdf
@pytest.mark.parametrize("fixture", _FIXTURES_LIST, ids=lambda p: p.stem)
def test_incremental_save_preserves_id0_and_updates_id1_like_pdfbox(
    fixture: Path, tmp_path: Path
) -> None:
    """The spec contract (ISO 32000-1 §14.4): on incremental update /ID[0] is
    preserved from the original and /ID[1] is changed. Verified on both PDFBox
    and pypdfbox outputs (byte values differ — time/random based — so we assert
    the *contract*, not equality)."""
    if not fixture.is_file():
        pytest.skip(f"fixture missing: {fixture}")

    src_ids = _py_id(fixture)
    assert src_ids is not None, "fixture lacks a 2-element /ID"
    src_id0, src_id1 = src_ids

    # --- Java oracle: confirm PDFBox's incremental contract -------------
    java_out = tmp_path / f"java_inc_{fixture.stem}.pdf"
    jf = _parse_probe(
        run_probe_text("FileIdProbe", "incremental", str(fixture), str(java_out))
    )
    assert jf["before_id0_hex"] == src_id0.hex().upper()
    assert jf.get("after_id_present") == "true"
    # PDFBox preserves /ID[0] and changes /ID[1].
    assert jf["after_id0_hex"] == jf["before_id0_hex"]
    assert jf["after_id1_hex"] != jf["before_id1_hex"]

    # --- pypdfbox: same contract ----------------------------------------
    py_out = tmp_path / f"py_inc_{fixture.stem}.pdf"
    _save_incremental_py(fixture, py_out)
    py_ids = _py_id(py_out)
    assert py_ids is not None, (
        "pypdfbox incremental save dropped the /ID array — the appended "
        "trailer must carry /ID"
    )
    inc_id0, inc_id1 = py_ids
    # /ID[0] preserved byte-for-byte (the permanent identifier).
    assert inc_id0 == src_id0, (
        "pypdfbox incremental save did not preserve the permanent /ID[0]"
    )
    # /ID[1] changed (the spec's "file has been updated" signal).
    assert inc_id1 != src_id1, (
        "pypdfbox incremental save did not update the changing /ID[1] — "
        "consumers cannot detect the file was modified"
    )

    # Both outputs structurally valid.
    j_rc, j_log = _qpdf_ok(java_out)
    p_rc, p_log = _qpdf_ok(py_out)
    assert j_rc <= 3, f"Java incremental failed qpdf (rc={j_rc}):\n{j_log}"
    assert p_rc <= 3, f"pypdfbox incremental failed qpdf (rc={p_rc}):\n{p_log}"


@requires_oracle
def test_incremental_save_does_not_mutate_in_memory_id(tmp_path: Path) -> None:
    """Regenerating /ID[1] for the appended trailer must not mutate the
    in-memory document's /ID (a subsequent re-save must still see the source
    array). We build the new array on a copied trailer dict, so the live
    document is untouched."""
    src = _FIXTURES / "pdfwriter" / "unencrypted.pdf"
    cos = Loader.load_pdf(src)
    doc = PDDocument(cos)
    out = tmp_path / "inc_no_mutate.pdf"
    try:
        trailer = cos.get_trailer()
        before = trailer.get_dictionary_object(_ID_NAME)
        assert isinstance(before, COSArray)
        before_id1 = before.get_object(1).get_bytes()
        cos.get_catalog().set_needs_to_be_updated(True)
        doc.save_incremental(str(out))
        # The live in-memory /ID[1] is unchanged after the append.
        after = trailer.get_dictionary_object(_ID_NAME)
        assert isinstance(after, COSArray)
        assert after.get_object(1).get_bytes() == before_id1
    finally:
        doc.close()
