"""Live PDFBox differential parity for content preservation across a
``Splitter.split`` partition.

The sibling ``test_merge_split_oracle.py`` already pins the *partition shape*
(part count + per-part page counts + qpdf validity). This module pins the
load-bearing complement: that each part's pages **preserve their text
content** after the split. A split that silently dropped a page's content
stream, swapped resources, or mis-assigned pages to parts would keep the page
counts intact yet corrupt the text — only a content-level compare catches it.

For both split granularities (default 1-page parts and N-page parts) we drive
Apache PDFBox's ``Splitter`` via the ``SplitContentProbe`` Java probe, which
emits, per part, the part's page count and the ``PDFTextStripper`` text of each
page within that part. pypdfbox runs the identical split and extracts the same
per-part / per-page text, and we assert:

* identical part count and per-part page counts (the partition);
* identical normalised text page-for-page within every part (content
  preserved and assigned to the right part);
* every pypdfbox part passes ``qpdf --check``.

Text is whitespace-stripped on both sides before comparison. We deliberately
do NOT compare inter-word spacing: PDFBox's ``PDFTextStripper`` and pypdfbox's
differ in how many spaces they synthesise across dot-leader / tab-stop runs
(e.g. a table-of-contents ``".... 5-1"`` vs ``"....5-1"``), a divergence that
lives entirely in the text-extraction module and is present in unsplit
extraction too — it is not a ``Splitter`` behaviour. Stripping whitespace keeps
this a faithful content-preservation pin on the ``Splitter`` while staying
agnostic to the text module's spacing heuristic; a genuinely dropped,
duplicated, or mis-assigned page still fails because its characters move or
vanish.
"""

from __future__ import annotations

import json
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

# Content-split cases: (id, fixture, split_at). Fixtures chosen for genuine,
# distinguishable per-page text so a mis-assigned or dropped page is visible.
_CASES = [
    ("toc8p_every1", "PDFBOX-5762-722238.pdf", 1),
    ("toc8p_every3", "PDFBOX-5762-722238.pdf", 3),
    ("endocrine3p_every1", "PDFBOX-5809-509329.pdf", 1),
    ("endocrine3p_every2", "PDFBOX-5809-509329.pdf", 2),
    ("generic4p_every2", "PDFBOX-4417-001031.pdf", 2),
    ("place6p_every2", "PDFBOX-5792-240045.pdf", 2),
]


def _normalize(text: str | None) -> str:
    """Remove all whitespace — mirrors the Java probe's ``normalize``. See the
    module docstring for why inter-word spacing is intentionally not compared
    (it's a text-module heuristic, not a Splitter behaviour)."""
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


def _split_py_content(
    src_path: Path, split_at: int, out_dir: Path
) -> list[dict]:
    """Split ``src_path`` at ``split_at`` through pypdfbox; return a list of
    ``{"pages": N, "text": [page0, page1, ...]}`` dicts (one per part) and save
    each part into ``out_dir/part_<i>.pdf``.

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
                texts: list[str] = []
                for p in range(page_count):
                    stripper = PDFTextStripper()
                    stripper.set_start_page(p + 1)
                    stripper.set_end_page(p + 1)
                    texts.append(_normalize(stripper.get_text(part)))
                result.append({"pages": page_count, "text": texts})
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
def test_split_preserves_content_matches_pdfbox(
    case_id: str, name: str, split_at: int, tmp_path: Path
) -> None:
    src = _FIXTURES / name
    if not src.is_file():
        pytest.skip(f"fixture missing: {src}")

    # --- Java oracle: split + per-part / per-page text -----------------
    java_raw = run_probe_text("SplitContentProbe", str(src), str(split_at))
    java_parts = json.loads(java_raw)["parts"]

    # --- pypdfbox: split + per-part / per-page text --------------------
    py_dir = tmp_path / f"py_{case_id}"
    py_parts = _split_py_content(src, split_at, py_dir)

    # (1) Same partition: part count + per-part page counts.
    assert [p["pages"] for p in py_parts] == [p["pages"] for p in java_parts], (
        f"split partition divergence for {case_id}:\n"
        f"  pypdfbox: {[p['pages'] for p in py_parts]}\n"
        f"  PDFBox:   {[p['pages'] for p in java_parts]}"
    )

    # (2) Identical text page-for-page within every part.
    assert py_parts == java_parts, (
        f"split content divergence for {case_id}:\n"
        f"  pypdfbox: {json.dumps(py_parts, ensure_ascii=False)}\n"
        f"  PDFBox:   {json.dumps(java_parts, ensure_ascii=False)}"
    )

    # (3) Every pypdfbox part is structurally valid.
    for i in range(len(py_parts)):
        rc, log = _qpdf_check(py_dir / f"part_{i}.pdf")
        assert rc <= 3, (
            f"pypdfbox split part {i} failed qpdf --check (rc={rc}):\n{log}"
        )


@requires_oracle
def test_split_content_concatenation_equals_source(tmp_path: Path) -> None:
    """Cross-check independent of part assignment: concatenating every part's
    per-page text (in part order, page order) reproduces the source document's
    full per-page text in order — the property a content-preserving split must
    hold regardless of where the chunk boundaries fall."""
    src = _FIXTURES / "PDFBOX-5762-722238.pdf"
    if not src.is_file():
        pytest.skip(f"fixture missing: {src}")

    # Source per-page text (the ground truth).
    doc = PDDocument.load(src)
    try:
        n = doc.get_number_of_pages()
        source_pages: list[str] = []
        for p in range(n):
            stripper = PDFTextStripper()
            stripper.set_start_page(p + 1)
            stripper.set_end_page(p + 1)
            source_pages.append(_normalize(stripper.get_text(doc)))
    finally:
        doc.close()

    py_parts = _split_py_content(src, 3, tmp_path / "concat")
    flattened = [text for part in py_parts for text in part["text"]]
    assert flattened == source_pages
