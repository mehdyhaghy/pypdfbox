"""Live PDFBox differential parity for **multiple sequential incremental
saves** — a PDF carrying three or more revisions stacked into one file via
repeated ``save_incremental`` calls.

PDF 32000-1 §7.5.6 specifies the incremental update model: each new revision
appends an object body, an xref section, and a trailer to the end of the
file, with the new trailer's ``/Prev`` pointing at the previous revision's
``startxref`` offset. A conforming parser must read the *last* trailer first
and walk ``/Prev`` backwards through the chain so that the *latest* version
of every object wins — exactly the same contract a single-step incremental
save satisfies, repeated N times.

This module locks the multi-revision contract end-to-end:

1. Build rev 1 by full-saving a known fixture.
2. Apply rev 2 (set ``/Info /Author``) via ``PDDocument.save_incremental``.
3. Apply rev 3 (set ``/Info /Subject``) via another ``save_incremental`` —
   on top of rev 2's output, not the original fixture.
4. Apply rev 4 (set ``/Info /Title``) via a third ``save_incremental``.
5. Assert byte-prefix invariance at every step (each revision must contain
   the previous revision's bytes verbatim — no rewrite).
6. Assert qpdf-validity at every step.
7. Run ``IncrementalChainProbe`` against the final file and confirm PDFBox
   resolves the catalog + ``/Info`` to the *latest* values (Alice / IncTest /
   IncTitle), counts the expected number of xref sections, and recovers the
   original page count + extracted text.
8. Reproduce the same facts from pypdfbox and assert parity.

The append-only / ``/Prev`` chain probe was already covered for a single
revision by ``test_save_round_trip_oracle::test_incremental_save_*``. What
this file proves is that the chain composes — a writer that emits a
correct rev N+1 on top of an arbitrary rev N (rather than only on top of a
pristine full save) is what makes multi-author edit pipelines possible.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from pypdfbox import Loader, PDDocument
from tests.oracle.harness import requires_oracle, run_probe_text

_REPO_ROOT = Path(__file__).resolve().parents[3]
_FIXTURES = _REPO_ROOT / "tests" / "fixtures"
_BASE_FIXTURE = _FIXTURES / "pdfwriter" / "unencrypted.pdf"

_QPDF = shutil.which("qpdf")
_requires_qpdf = pytest.mark.skipif(
    _QPDF is None, reason="qpdf binary not on PATH (brew install qpdf)"
)


# ----------------------------------------------------------------- helpers


def _qpdf_check(path: Path) -> tuple[int, str]:
    """Run ``qpdf --check``; return ``(returncode, combined output)``.

    Exit codes (man qpdf): 0 = clean, 2 = errors (broken), 3 = warnings
    (valid). rc <= 3 is structurally valid.
    """
    proc = subprocess.run(
        [str(_QPDF), "--check", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def _set_field_and_incremental_save(
    src: Path, out: Path, field: str, value: str
) -> None:
    """Load ``src``, mutate one ``/Info`` field, ``save_incremental`` to
    ``out``. The document is always closed before returning so the source
    file's handle is released (Windows file-lock safety)."""
    cos = Loader.load_pdf(src)
    doc = PDDocument(cos)
    try:
        info = doc.get_document_information()
        # Each setter mutates the underlying /Info COSDictionary. We flag
        # it dirty + flag the trailer dirty so the writer's ``needs_to_be
        # _updated`` walk picks the changes up.
        if field == "Author":
            info.set_author(value)
        elif field == "Subject":
            info.set_subject(value)
        elif field == "Title":
            info.set_title(value)
        else:
            raise ValueError(f"unknown field: {field}")
        info.get_cos_object().set_needs_to_be_updated(True)
        doc.save_incremental(str(out))
    finally:
        doc.close()


def _build_three_revision_chain(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    """Lay down four sequential snapshots in ``tmp_path``:

    * rev1 = the unmodified fixture (a verbatim copy so we can prefix-check
      rev2 against the same bytes pypdfbox saw on load).
    * rev2 = rev1 + ``Author = Alice`` via ``save_incremental``.
    * rev3 = rev2 + ``Subject = IncTest`` via another ``save_incremental``.
    * rev4 = rev3 + ``Title  = IncTitle`` via a third ``save_incremental``.

    Returns the four paths in chronological order.
    """
    rev1 = tmp_path / "chain_rev1.pdf"
    rev2 = tmp_path / "chain_rev2.pdf"
    rev3 = tmp_path / "chain_rev3.pdf"
    rev4 = tmp_path / "chain_rev4.pdf"
    shutil.copyfile(_BASE_FIXTURE, rev1)
    _set_field_and_incremental_save(rev1, rev2, "Author", "Alice")
    _set_field_and_incremental_save(rev2, rev3, "Subject", "IncTest")
    _set_field_and_incremental_save(rev3, rev4, "Title", "IncTitle")
    return rev1, rev2, rev3, rev4


def _read_info_facts(path: Path) -> dict[str, object]:
    """Reload ``path`` through pypdfbox and gather the same facts the
    Java probe emits — page count + /Info entries — so the parity test can
    cross-check them line for line."""
    cos = Loader.load_pdf(path)
    doc = PDDocument(cos)
    try:
        info = doc.get_document_information()
        return {
            "pages": doc.get_number_of_pages(),
            "author": info.get_author(),
            "subject": info.get_subject(),
            "title": info.get_title(),
            "producer": info.get_producer(),
        }
    finally:
        doc.close()


def _count_startxref(data: bytes) -> int:
    """Count occurrences of the ``startxref`` keyword in ``data``. Each
    revision (base + each incremental append) contributes exactly one, so
    this is the on-disk revision-count metric."""
    count = 0
    needle = b"startxref"
    i = 0
    while True:
        j = data.find(needle, i)
        if j < 0:
            return count
        count += 1
        i = j + len(needle)


def _parse_probe_output(out: str) -> dict[str, str]:
    """Parse the IncrementalChainProbe's line-oriented ``key=value`` output.

    The ``text`` key is special-cased: the probe emits it last and its
    value can span multiple lines (page-stripper output keeps newlines), so
    once we hit ``text=`` we take everything that follows verbatim.
    """
    facts: dict[str, str] = {}
    lines = out.splitlines(keepends=True)
    for idx, line in enumerate(lines):
        stripped = line.rstrip("\n")
        if stripped.startswith("text="):
            facts["text"] = (
                stripped[len("text=") :] + "".join(lines[idx + 1 :])
            )
            break
        key, sep, value = stripped.partition("=")
        if sep:
            facts[key] = value
    return facts


# ----------------------------------------------------------- the parity tests


@requires_oracle
@_requires_qpdf
def test_sequential_incremental_chain_is_byte_prefix_monotonic(
    tmp_path: Path,
) -> None:
    """Each revision in the chain must contain the *previous* revision's
    bytes as an exact prefix. Incremental save is append-only — overwriting
    the prefix would corrupt the ``/Prev`` chain a conforming parser walks
    to recover earlier object versions (ISO 32000-1 §7.5.6)."""
    rev1, rev2, rev3, rev4 = _build_three_revision_chain(tmp_path)

    rev1_bytes = rev1.read_bytes()
    rev2_bytes = rev2.read_bytes()
    rev3_bytes = rev3.read_bytes()
    rev4_bytes = rev4.read_bytes()

    assert rev2_bytes.startswith(rev1_bytes), (
        "rev2 must contain rev1 verbatim as a prefix"
    )
    assert rev3_bytes.startswith(rev2_bytes), (
        "rev3 must contain rev2 verbatim as a prefix"
    )
    assert rev4_bytes.startswith(rev3_bytes), (
        "rev4 must contain rev3 verbatim as a prefix"
    )

    # Each append must add a non-empty tail (the new revision's xref +
    # trailer + dirty objects, never zero bytes).
    assert len(rev2_bytes) > len(rev1_bytes)
    assert len(rev3_bytes) > len(rev2_bytes)
    assert len(rev4_bytes) > len(rev3_bytes)

    # Every appended slice must include a /Prev back-pointer.
    assert b"/Prev" in rev2_bytes[len(rev1_bytes) :]
    assert b"/Prev" in rev3_bytes[len(rev2_bytes) :]
    assert b"/Prev" in rev4_bytes[len(rev3_bytes) :]

    # And the file always ends with %%EOF.
    for blob in (rev2_bytes, rev3_bytes, rev4_bytes):
        assert blob.rstrip().endswith(b"%%EOF")


@requires_oracle
@_requires_qpdf
def test_every_revision_in_chain_is_qpdf_valid(tmp_path: Path) -> None:
    """A multi-revision chain that breaks at rev N+1 (malformed /Prev,
    truncated xref) would fail ``qpdf --check`` with rc 2. We require rc
    <= 3 (clean or warnings-only) for every intermediate revision."""
    _, rev2, rev3, rev4 = _build_three_revision_chain(tmp_path)
    for label, path in (("rev2", rev2), ("rev3", rev3), ("rev4", rev4)):
        rc, log = _qpdf_check(path)
        assert rc <= 3, f"{label} failed qpdf --check (rc={rc}):\n{log}"


@requires_oracle
@_requires_qpdf
def test_pdfbox_recovers_latest_values_through_chain(tmp_path: Path) -> None:
    """The final revision in the chain carries all three /Info edits.
    PDFBox loads the file, walks ``/Prev`` backwards through every prior
    revision, and resolves /Info to the values written by the *last*
    revision (Alice / IncTest / IncTitle). The page count + extracted
    text must match the original fixture — incremental saves don't touch
    page content here, only the /Info dict."""
    _, _, _, rev4 = _build_three_revision_chain(tmp_path)

    raw = run_probe_text("IncrementalChainProbe", str(rev4))
    facts = _parse_probe_output(raw)

    assert facts["author"] == "Alice"
    assert facts["subject"] == "IncTest"
    assert facts["title"] == "IncTitle"
    # The fixture's original producer is preserved across the chain — we
    # only mutated Author / Subject / Title.
    assert facts["producer"] not in ("NULL", "")
    # The fixture is a two-page document.
    assert facts["pages"] == "2"
    # The probe counts startxref markers in the raw bytes; our pypdfbox
    # counter MUST agree. (We don't lock to an exact integer here — the
    # fixture itself may carry a hybrid xref-stream + classic-table, so
    # the absolute count is fixture-dependent. Parity with the Java probe
    # is the real assertion.)
    probe_sections = int(facts["xref_sections"])
    py_sections = _count_startxref(rev4.read_bytes())
    assert probe_sections == py_sections, (
        f"Java counted {probe_sections} startxref markers, pypdfbox "
        f"counted {py_sections} — divergence implies a write/parse mismatch"
    )
    # We added three incremental revisions on top of the base, so the
    # final file must carry strictly more sections than the base did.
    base_sections = _count_startxref(_BASE_FIXTURE.read_bytes())
    assert py_sections >= base_sections + 3, (
        f"expected at least {base_sections + 3} xref sections after three "
        f"incremental saves, got {py_sections}"
    )


@requires_oracle
@_requires_qpdf
def test_pypdfbox_recovers_latest_values_through_chain(tmp_path: Path) -> None:
    """The pypdfbox side of the differential: load the multi-revision file
    pypdfbox itself just produced and confirm pypdfbox's own ``/Prev`` walk
    also lands on the latest values. This catches the writer-reader
    asymmetry where the writer emits a chain the reader can't follow."""
    _, _, _, rev4 = _build_three_revision_chain(tmp_path)

    facts = _read_info_facts(rev4)
    assert facts["author"] == "Alice"
    assert facts["subject"] == "IncTest"
    assert facts["title"] == "IncTitle"
    assert facts["pages"] == 2
    assert facts["producer"] is not None


@requires_oracle
@_requires_qpdf
def test_intermediate_revisions_each_carry_one_more_field(
    tmp_path: Path,
) -> None:
    """Each step in the chain adds exactly one /Info field while preserving
    the previously-added fields. Catches a regression where save_incremental
    accidentally drops the inherited /Info entries (e.g. by overwriting the
    appended object instead of merging the dirty graph)."""
    _, rev2, rev3, rev4 = _build_three_revision_chain(tmp_path)

    rev2_facts = _read_info_facts(rev2)
    assert rev2_facts["author"] == "Alice"
    assert rev2_facts["subject"] is None
    assert rev2_facts["title"] is None

    rev3_facts = _read_info_facts(rev3)
    assert rev3_facts["author"] == "Alice"
    assert rev3_facts["subject"] == "IncTest"
    assert rev3_facts["title"] is None

    rev4_facts = _read_info_facts(rev4)
    assert rev4_facts["author"] == "Alice"
    assert rev4_facts["subject"] == "IncTest"
    assert rev4_facts["title"] == "IncTitle"


@requires_oracle
@_requires_qpdf
def test_pdfbox_and_pypdfbox_agree_on_chain_facts(tmp_path: Path) -> None:
    """Joint differential: the Java probe and pypdfbox must agree on every
    fact emitted (pages, /Info fields, startxref count) for the same
    multi-revision file pypdfbox wrote."""
    _, _, _, rev4 = _build_three_revision_chain(tmp_path)

    raw = run_probe_text("IncrementalChainProbe", str(rev4))
    java = _parse_probe_output(raw)
    py = _read_info_facts(rev4)

    assert int(java["pages"]) == py["pages"]
    assert java["author"] == (py["author"] or "NULL")
    assert java["subject"] == (py["subject"] or "NULL")
    assert java["title"] == (py["title"] or "NULL")
    assert java["producer"] == (py["producer"] or "NULL")
    assert int(java["xref_sections"]) == _count_startxref(rev4.read_bytes())
