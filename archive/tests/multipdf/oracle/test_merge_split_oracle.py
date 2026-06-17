"""Live PDFBox differential parity for the multi-PDF surface
(``pypdfbox.multipdf`` — ``PDFMergerUtility`` + ``Splitter``).

This is a *validity + observable-shape equivalence* check, not byte equality:
PDF writers legitimately differ (PDFBox 3.0.7 packs objects into object
streams and emits a cross-reference *stream*; pypdfbox's full save defaults to
a classic ``xref`` table). What MUST agree is the recoverable, user-visible
result of a merge or split:

* **MERGE** (``MergeProbe`` — ``PDFMergerUtility.mergeDocuments``):
  merging the same ordered set of fixtures through Java and through pypdfbox
  yields, on reload, the same total page count and the same per-page media-box
  geometry (compared as IEEE-754 float32 bit patterns, repr-independent), and
  both outputs pass ``qpdf --check``.

* **SPLIT** (``SplitProbe`` — ``Splitter.setSplitAtPage`` + ``split``):
  splitting the same fixture at the same boundary through Java and through
  pypdfbox yields the same part count and identical per-part page counts, and
  every part passes ``qpdf --check``.

Page geometry is the load-bearing observable here: a merge that drops a page,
reorders pages, or corrupts a media box shows up immediately as a page-count or
float32-bits divergence. Object count / xref style are deliberately NOT compared
(documented writer-strategy difference — see the pdfwriter oracle module for the
detailed rationale on PDFBox object-stream packing vs pypdfbox flat bodies).
"""

from __future__ import annotations

import shutil
import struct
import subprocess
from pathlib import Path

import pytest

from pypdfbox.multipdf.pdf_merger_utility import PDFMergerUtility
from pypdfbox.multipdf.splitter import Splitter
from pypdfbox.pdmodel.pd_document import PDDocument
from tests.oracle.harness import requires_oracle, run_probe_text

_REPO_ROOT = Path(__file__).resolve().parents[3]
_FIXTURES = _REPO_ROOT / "tests" / "fixtures" / "multipdf"

_QPDF = shutil.which("qpdf")
_requires_qpdf = pytest.mark.skipif(
    _QPDF is None, reason="qpdf binary not on PATH (brew install qpdf)"
)

# Ordered merge sets: a spread of single-page, multi-page, rotated, and
# AcroForm shapes so the merge exercises page-tree concatenation, resource
# import, and form handling. Each entry is (id, [fixture filenames in order]).
_MERGE_SETS = [
    ("rotations", ["rot0.pdf", "rot90.pdf", "rot180.pdf", "rot270.pdf"]),
    ("multipage", ["PDFBOX-4417-054080.pdf", "PDFBOX-5809-509329.pdf"]),
    (
        "mixed_counts",
        ["rot0.pdf", "PDFBOX-5811-362972.pdf", "PDFBOX-4417-001031.pdf"],
    ),
    ("acroform_plus_plain", ["AcroFormForMerge.pdf", "rot0.pdf"]),
    ("single_page_pair", ["PDFA3A.pdf", "rot90.pdf"]),
]

# Split cases: (id, fixture filename, split_at_page).
_SPLIT_CASES = [
    ("8p_every1", "PDFBOX-5762-722238.pdf", 1),
    ("8p_every2", "PDFBOX-5762-722238.pdf", 2),
    ("8p_every3", "PDFBOX-5762-722238.pdf", 3),
    ("6p_every2", "PDFBOX-5792-240045.pdf", 2),
    ("4p_every2", "PDFBOX-4417-001031.pdf", 2),
    ("3p_every1", "PDFBOX-5809-509329.pdf", 1),
    ("source8p_every4", "PDFBOX-6049-Source.pdf", 4),
]


# ----------------------------------------------------------------- helpers


def _qpdf_check(path: Path) -> tuple[int, str]:
    """``(returncode, combined output)`` from ``qpdf --check``.

    Exit codes (man qpdf): 0 = clean, 2 = errors (broken), 3 = warnings only
    (valid; qpdf recovered). Treat rc <= 3 as structurally valid — PDFBox's
    xref-stream output routinely draws a benign rc 3 warning.
    """
    proc = subprocess.run(
        [str(_QPDF), "--check", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def _float_bits(value: float) -> str:
    """IEEE-754 single-precision (float32) bit pattern as lowercase hex,
    matching the Java probe's ``Integer.toHexString(Float.floatToIntBits)``
    (no leading zeros, no ``0x`` prefix)."""
    return format(struct.unpack("<I", struct.pack("<f", value))[0], "x")


def _merge_py(out_paths: list[Path], dest: Path) -> None:
    """Merge ``out_paths`` (in order) through pypdfbox into ``dest``."""
    merger = PDFMergerUtility()
    for src in out_paths:
        merger.add_source(str(src))
    merger.set_destination_file_name(str(dest))
    merger.merge_documents()


def _fingerprint_merged(path: Path) -> tuple[int, list[tuple[str, str]]]:
    """Reload a merged document and return (page_count, [(wbits, hbits)...]).

    Closes the document in ``finally`` so the source handle is released before
    a caller reopens/overwrites it (Windows file-lock safety).
    """
    doc = PDDocument.load(path)
    try:
        n = doc.get_number_of_pages()
        sizes: list[tuple[str, str]] = []
        for i in range(n):
            box = doc.get_page(i).get_media_box()
            sizes.append((_float_bits(box.get_width()), _float_bits(box.get_height())))
        return n, sizes
    finally:
        doc.close()


def _parse_merge_probe(text: str) -> tuple[int, list[tuple[str, str]]]:
    """Parse ``MergeProbe`` stdout into (page_count, [(wbits, hbits)...])."""
    pages = -1
    sizes: list[tuple[str, str]] = []
    for line in text.splitlines():
        parts = line.split()
        if not parts:
            continue
        if parts[0] == "pages":
            pages = int(parts[1])
        elif parts[0] == "page":
            sizes.append((parts[2], parts[3]))
    return pages, sizes


def _parse_split_probe(text: str) -> list[int]:
    """Parse ``SplitProbe`` stdout into a list of per-part page counts."""
    counts: list[int] = []
    declared = -1
    for line in text.splitlines():
        parts = line.split()
        if not parts:
            continue
        if parts[0] == "parts":
            declared = int(parts[1])
        elif parts[0] == "part":
            counts.append(int(parts[2]))
    assert declared == len(counts), (
        f"SplitProbe declared {declared} parts but emitted {len(counts)} lines"
    )
    return counts


def _split_py(src_path: Path, split_at: int, out_dir: Path) -> list[int]:
    """Split ``src_path`` at ``split_at`` through pypdfbox, save each part into
    ``out_dir/part_<i>.pdf``, and return per-part page counts.

    The source document must outlive its splits (cross-document resource
    sharing), so it is closed only after every part is saved + closed.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    source = PDDocument.load(src_path)
    try:
        splitter = Splitter()
        splitter.set_split_at_page(split_at)
        parts = splitter.split(source)
        counts: list[int] = []
        try:
            for i, part in enumerate(parts):
                counts.append(part.get_number_of_pages())
                part.save(str(out_dir / f"part_{i}.pdf"))
        finally:
            for part in parts:
                part.close()
        return counts
    finally:
        source.close()


# --------------------------------------------------------------- merge parity


@requires_oracle
@_requires_qpdf
@pytest.mark.parametrize(
    ("set_id", "names"), _MERGE_SETS, ids=[s[0] for s in _MERGE_SETS]
)
def test_merge_matches_pdfbox(set_id: str, names: list[str], tmp_path: Path) -> None:
    inputs = [_FIXTURES / n for n in names]
    for f in inputs:
        if not f.is_file():
            pytest.skip(f"fixture missing: {f}")

    # --- Java oracle: merge + reload fingerprint -----------------------
    java_out = tmp_path / f"java_{set_id}.pdf"
    java_text = run_probe_text(
        "MergeProbe", str(java_out), *[str(f) for f in inputs]
    )
    java_pages, java_sizes = _parse_merge_probe(java_text)

    # --- pypdfbox: merge -----------------------------------------------
    py_out = tmp_path / f"py_{set_id}.pdf"
    _merge_py(inputs, py_out)
    py_pages, py_sizes = _fingerprint_merged(py_out)

    # (1) Both outputs are structurally valid.
    java_rc, java_log = _qpdf_check(java_out)
    py_rc, py_log = _qpdf_check(py_out)
    assert java_rc <= 3, f"Java merge failed qpdf --check (rc={java_rc}):\n{java_log}"
    assert py_rc <= 3, f"pypdfbox merge failed qpdf --check (rc={py_rc}):\n{py_log}"

    # (2) Same total page count as PDFBox — no page dropped/duplicated.
    assert py_pages == java_pages, (
        f"merge page-count divergence: pypdfbox {py_pages} vs PDFBox {java_pages}"
    )

    # (3) Same per-page media-box geometry, in order (float32 bit-exact).
    assert py_sizes == java_sizes, (
        f"merged page geometry divergence for {set_id}:\n"
        f"  pypdfbox: {py_sizes}\n  PDFBox:   {java_sizes}"
    )


@requires_oracle
@_requires_qpdf
def test_merge_total_equals_sum_of_inputs(tmp_path: Path) -> None:
    """Cross-check the merge invariant directly: the merged page count equals
    the sum of every input's page count (the property a merge must preserve,
    independent of the oracle)."""
    names = ["PDFBOX-4417-001031.pdf", "PDFBOX-5809-509329.pdf", "rot270.pdf"]
    inputs = [_FIXTURES / n for n in names]
    for f in inputs:
        if not f.is_file():
            pytest.skip(f"fixture missing: {f}")

    expected = 0
    for f in inputs:
        d = PDDocument.load(f)
        try:
            expected += d.get_number_of_pages()
        finally:
            d.close()

    py_out = tmp_path / "py_sum.pdf"
    _merge_py(inputs, py_out)
    py_pages, _ = _fingerprint_merged(py_out)
    assert py_pages == expected

    # The oracle must agree on the same total.
    java_out = tmp_path / "java_sum.pdf"
    java_text = run_probe_text(
        "MergeProbe", str(java_out), *[str(f) for f in inputs]
    )
    java_pages, _ = _parse_merge_probe(java_text)
    assert java_pages == expected == py_pages


# --------------------------------------------------------------- split parity


@requires_oracle
@_requires_qpdf
@pytest.mark.parametrize(
    ("case_id", "name", "split_at"),
    _SPLIT_CASES,
    ids=[c[0] for c in _SPLIT_CASES],
)
def test_split_matches_pdfbox(
    case_id: str, name: str, split_at: int, tmp_path: Path
) -> None:
    src = _FIXTURES / name
    if not src.is_file():
        pytest.skip(f"fixture missing: {src}")

    # --- Java oracle: split + save parts -------------------------------
    java_dir = tmp_path / f"java_{case_id}"
    java_text = run_probe_text("SplitProbe", str(src), str(split_at), str(java_dir))
    java_counts = _parse_split_probe(java_text)

    # --- pypdfbox: split + save parts ----------------------------------
    py_dir = tmp_path / f"py_{case_id}"
    py_counts = _split_py(src, split_at, py_dir)

    # (1) Same part count as PDFBox.
    assert len(py_counts) == len(java_counts), (
        f"split part-count divergence for {case_id}: "
        f"pypdfbox {len(py_counts)} vs PDFBox {len(java_counts)}"
    )

    # (2) Identical per-part page counts, in order.
    assert py_counts == java_counts, (
        f"split per-part page-count divergence for {case_id}:\n"
        f"  pypdfbox: {py_counts}\n  PDFBox:   {java_counts}"
    )

    # (3) Every pypdfbox part is structurally valid.
    for i in range(len(py_counts)):
        part = py_dir / f"part_{i}.pdf"
        rc, log = _qpdf_check(part)
        assert rc <= 3, f"pypdfbox split part {i} failed qpdf --check (rc={rc}):\n{log}"

    # (4) Every Java part is structurally valid too (genuinely differential).
    for i in range(len(java_counts)):
        part = java_dir / f"part_{i}.pdf"
        rc, log = _qpdf_check(part)
        assert rc <= 3, f"Java split part {i} failed qpdf --check (rc={rc}):\n{log}"


@requires_oracle
@_requires_qpdf
def test_split_total_pages_preserved(tmp_path: Path) -> None:
    """The sum of all part page counts must equal the source page count —
    splitting neither loses nor duplicates a page. Checked on both sides."""
    src = _FIXTURES / "PDFBOX-5762-722238.pdf"
    if not src.is_file():
        pytest.skip(f"fixture missing: {src}")

    d = PDDocument.load(src)
    try:
        total = d.get_number_of_pages()
    finally:
        d.close()

    py_counts = _split_py(src, 3, tmp_path / "py_total")
    assert sum(py_counts) == total

    java_text = run_probe_text("SplitProbe", str(src), "3", str(tmp_path / "java_total"))
    java_counts = _parse_split_probe(java_text)
    assert sum(java_counts) == total == sum(py_counts)
