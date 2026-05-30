"""Live PDFBox differential parity for ``Splitter.split`` at the split-at-page
*boundary* intervals (``pypdfbox.multipdf.splitter.Splitter``).

The sibling ``test_merge_split_oracle.py`` pins the partition shape (part count
+ per-part page counts + qpdf validity) at "interior" intervals (every 1, 2, 3
pages). ``test_split_content_oracle.py`` pins full per-page text preservation.
This module pins the three *boundary* intervals that determine the partition
arithmetic itself, plus a first-page identity signal that catches a mis-ordered
partition the page-count compare cannot:

* **interval 1** — one document per page (the upstream default): ``pages`` parts;
* **interval N** (1 < N < pages) — ``ceil(pages / N)`` parts, the last one
  shorter when ``pages`` is not a multiple of N;
* **interval > pages** — exactly one document carrying *every* page (the case
  the interior-interval pins never reach). PDFBox's ``createNewDocumentIfNecessary``
  only opens a new chunk when ``(pageNumber + 1 - startPage) % splitLength == 0``,
  so an oversized ``splitLength`` never triggers a second chunk.

For each interval we drive Apache PDFBox's ``Splitter`` via the ``SplitterProbe``
Java probe (part count + per-part page count + normalised first-page text) and
the identical pypdfbox split, then assert:

* identical part count and per-part page counts (the partition);
* identical normalised first-page text per part (the right source page landed
  first in the right part);
* every pypdfbox part passes ``qpdf --check``.

First-page text is whitespace-stripped on both sides — the inter-word spacing
divergence between the two text strippers lives in the text module, not the
Splitter (see ``test_split_content_oracle.py`` for the full rationale).
"""

from __future__ import annotations

import json
import math
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from pypdfbox.multipdf.splitter import Splitter
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.text.pdf_text_stripper import PDFTextStripper
from tests.oracle.harness import requires_oracle, run_probe_text

_REPO_ROOT = Path(__file__).resolve().parents[3]
_FIXTURES = _REPO_ROOT / "tests" / "fixtures" / "multipdf"

_QPDF = shutil.which("qpdf")
_requires_qpdf = pytest.mark.skipif(
    _QPDF is None, reason="qpdf binary not on PATH (brew install qpdf)"
)

_WS = re.compile(r"\s+")

# Boundary-interval cases: (id, fixture, split_at). Each fixture has genuine
# per-page text so the first-page identity signal is meaningful. The interval
# is chosen relative to the fixture's page count to hit the three boundaries:
#   every1   -> interval 1, one doc per page
#   everyN   -> 1 < N < pages, ceil(pages / N) docs
#   oversize -> interval > pages, exactly one doc with every page
_CASES = [
    ("3p_every1", "PDFBOX-5809-509329.pdf", 1),
    ("3p_every2", "PDFBOX-5809-509329.pdf", 2),
    ("3p_oversize", "PDFBOX-5809-509329.pdf", 99),
    ("8p_every1", "PDFBOX-5762-722238.pdf", 1),
    ("8p_every3", "PDFBOX-5762-722238.pdf", 3),
    ("8p_oversize", "PDFBOX-5762-722238.pdf", 100),
    ("4p_every3", "PDFBOX-4417-001031.pdf", 3),
    ("4p_oversize", "PDFBOX-4417-001031.pdf", 50),
]


def _normalize(text: str | None) -> str:
    """Strip all whitespace — mirrors the Java probe's ``normalize``."""
    if not text:
        return ""
    return _WS.sub("", text)


def _qpdf_check(path: Path) -> tuple[int, str]:
    """``(returncode, combined output)`` from ``qpdf --check`` (rc <= 3 ok)."""
    proc = subprocess.run(
        [str(_QPDF), "--check", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def _split_py(src_path: Path, split_at: int, out_dir: Path) -> list[dict]:
    """Split ``src_path`` at ``split_at`` through pypdfbox; return a list of
    ``{"pages": N, "first": firstPageText}`` dicts (one per part) and save each
    part into ``out_dir/part_<i>.pdf``.

    The source document must outlive its splits (cross-document resource
    sharing), so it is closed only after every part has been read + saved.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    source = PDDocument.load(src_path)
    try:
        splitter = Splitter()
        splitter.set_split_at_page(split_at)
        parts = splitter.split(source)
        result: list[dict] = []
        try:
            for i, part in enumerate(parts):
                page_count = part.get_number_of_pages()
                first = ""
                if page_count > 0:
                    stripper = PDFTextStripper()
                    stripper.set_start_page(1)
                    stripper.set_end_page(1)
                    first = _normalize(stripper.get_text(part))
                result.append({"pages": page_count, "first": first})
                part.save(str(out_dir / f"part_{i}.pdf"))
        finally:
            for part in parts:
                part.close()
        return result
    finally:
        source.close()


@requires_oracle
@_requires_qpdf
@pytest.mark.parametrize(
    ("case_id", "name", "split_at"),
    _CASES,
    ids=[c[0] for c in _CASES],
)
def test_split_boundary_intervals_match_pdfbox(
    case_id: str, name: str, split_at: int, tmp_path: Path
) -> None:
    src = _FIXTURES / name
    if not src.is_file():
        pytest.skip(f"fixture missing: {src}")

    # Source page count — used to assert the partition arithmetic the
    # boundary intervals are about.
    d = PDDocument.load(src)
    try:
        total = d.get_number_of_pages()
    finally:
        d.close()

    # --- Java oracle: partition + per-part first-page text -------------
    java_raw = run_probe_text("SplitterProbe", str(src), str(split_at))
    java_parts = json.loads(java_raw)["parts"]

    # --- pypdfbox: identical split -------------------------------------
    py_dir = tmp_path / f"py_{case_id}"
    py_parts = _split_py(src, split_at, py_dir)

    # (1) Same partition: part count + per-part page counts, in order.
    py_counts = [p["pages"] for p in py_parts]
    java_counts = [p["pages"] for p in java_parts]
    assert py_counts == java_counts, (
        f"split partition divergence for {case_id}:\n"
        f"  pypdfbox: {py_counts}\n  PDFBox:   {java_counts}"
    )

    # (2) The partition matches the documented arithmetic on BOTH sides.
    expected_parts = math.ceil(total / split_at)
    assert len(py_counts) == expected_parts == len(java_counts), (
        f"part count for {case_id}: pypdfbox {len(py_counts)}, PDFBox "
        f"{len(java_counts)}, expected ceil({total}/{split_at})={expected_parts}"
    )
    assert sum(py_counts) == total, "split must neither drop nor duplicate a page"

    # (3) Identical normalised first-page text per part — the right source
    #     page landed first in the right part.
    assert py_parts == java_parts, (
        f"split first-page identity divergence for {case_id}:\n"
        f"  pypdfbox: {json.dumps(py_parts, ensure_ascii=False)}\n"
        f"  PDFBox:   {json.dumps(java_parts, ensure_ascii=False)}"
    )

    # (4) Every pypdfbox part is structurally valid.
    for i in range(len(py_parts)):
        rc, log = _qpdf_check(py_dir / f"part_{i}.pdf")
        assert rc <= 3, (
            f"pypdfbox split part {i} failed qpdf --check (rc={rc}):\n{log}"
        )


@requires_oracle
@_requires_qpdf
def test_oversize_interval_yields_single_part_matches_pdfbox(
    tmp_path: Path,
) -> None:
    """A split-at-page interval larger than the source page count produces a
    *single* document carrying every page — on both sides. Direct pin for the
    boundary the interior-interval cases never reach (``splitLength`` never
    triggers a second chunk)."""
    src = _FIXTURES / "PDFBOX-5762-722238.pdf"
    if not src.is_file():
        pytest.skip(f"fixture missing: {src}")

    d = PDDocument.load(src)
    try:
        total = d.get_number_of_pages()
    finally:
        d.close()

    java_parts = json.loads(
        run_probe_text("SplitterProbe", str(src), str(total + 5))
    )["parts"]
    py_parts = _split_py(src, total + 5, tmp_path / "oversize")

    assert len(py_parts) == 1, "oversize interval must yield exactly one part"
    assert py_parts[0]["pages"] == total
    assert [p["pages"] for p in py_parts] == [p["pages"] for p in java_parts]
    assert py_parts == java_parts
