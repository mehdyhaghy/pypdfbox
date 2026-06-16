"""Live PDFBox differential fuzz for ``Splitter`` CONFIGURATION edge cases
(``pypdfbox.multipdf.splitter.Splitter``) — wave 1551, agent D.

The sibling Splitter oracle modules each pin one facet on disk fixtures:
``test_splitter_oracle`` (partition + first-page text at the three boundary
intervals), ``test_splitter_inherit_oracle`` (per-page geometry materialisation),
``test_split_content_oracle`` (full per-page text), ``test_merge_split_oracle``
(interior intervals + qpdf validity). This module is the *combinatorial config
fuzz* layer: it drives ~30 SETTER configurations through both Java PDFBox 3.0.7
and pypdfbox on byte-identical pypdfbox-built source documents, and compares a
single STABLE fingerprint of the resulting document list — result count,
per-result page count, and the resolved MediaBox + Rotate of the first result's
first page (so an inherited-attribute drop or a mis-rounded geometry would show).

Fuzz angles NOT covered by the sibling modules:
  * ``setSplitAtPage(n)`` with n = 1 / 2 / 3 / 4 / larger-than-pages, AND the
    invalid n = 0 (both engines must reject);
  * ``setStartPage`` / ``setEndPage`` bounds: start-only, end-only, a
    sub-range, start past the last page (0 results), end past the last page
    (clamped to all remaining), single-page range (start==end), and the invalid
    start>end ordering (both engines must reject);
  * start clamp interacting with the split modulo (``max(1, start)``);
  * a single-page source and a genuinely zero-page source (0 results on both);
  * inherited /MediaBox + /Rotate (set on the /Pages node, not the leaf) must
    survive onto the split result's first page on BOTH sides.

Documented honest divergence (NOT a bug): on an invalid configuration PDFBox
throws ``IllegalArgumentException`` while pypdfbox raises ``ValueError`` — the
language-idiomatic equivalent. Both reject the same inputs, so the fingerprint
collapses any rejection to the verdict ``err`` and the per-case assertion below
checks that BOTH sides land in the rejecting branch (see ``_VERDICT``).

Source PDFs are produced by pypdfbox so both engines see identical input. Bytes
/ object counts are never compared — only recoverable structural facts.
The Java side runs through the ``SplitterFuzzProbe`` probe.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.cos import COSArray, COSInteger, COSName
from pypdfbox.multipdf.splitter import Splitter
from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.pdmodel.common import PDRectangle
from tests.oracle.harness import requires_oracle, run_probe_text

_MEDIA_BOX = COSName.get_pdf_name("MediaBox")
_ROTATE = COSName.get_pdf_name("Rotate")


# ----------------------------------------------------------------- builders


def _plain(out_dir: Path, n_pages: int, rotate: int | None = None) -> Path:
    """A document with ``n_pages`` Letter pages, optionally rotated."""
    suffix = f"_rot{rotate}" if rotate is not None else ""
    p = out_dir / f"plain_{n_pages}{suffix}.pdf"
    doc = PDDocument()
    for _ in range(n_pages):
        page = PDPage(PDRectangle.LETTER)
        if rotate is not None:
            page.set_rotation(rotate)
        doc.add_page(page)
    doc.save(str(p))
    doc.close()
    return p


def _zero_page(out_dir: Path) -> Path:
    """A genuinely 0-page source: valid catalog + empty /Pages tree."""
    p = out_dir / "zero.pdf"
    doc = PDDocument()
    doc.save(str(p))
    doc.close()
    return p


def _inherited_geometry(out_dir: Path, n_pages: int = 3) -> Path:
    """A document whose pages inherit /MediaBox (300x400) and /Rotate (180)
    from the /Pages node — neither key lives on a leaf page dict. The split
    result's first page must still carry the resolved values."""
    p = out_dir / "inherited.pdf"
    doc = PDDocument()
    for _ in range(n_pages):
        page = PDPage()
        doc.add_page(page)
        page.get_cos_object().remove_item(_MEDIA_BOX)
    pages_node = doc.get_pages().get_cos_object()
    mb = COSArray()
    for v in (0, 0, 300, 400):
        mb.add(COSInteger.get(v))
    pages_node.set_item(_MEDIA_BOX, mb)
    pages_node.set_item(_ROTATE, COSInteger.get(180))
    doc.save(str(p))
    doc.close()
    return p


# ----------------------------------------------------------------- pypdfbox run


def _split_py(src_path: Path, config: str) -> str:
    """Run pypdfbox's ``Splitter`` over ``config`` and return the SAME
    fingerprint string the ``SplitterFuzzProbe`` emits. ``config`` is the
    semicolon-separated ``split=/start=/end=`` grammar the probe parses."""
    split = start = end = None
    for tok in config.split(";"):
        tok = tok.strip()
        if not tok:
            continue
        key, _, raw = tok.partition("=")
        val = int(raw)
        if key.strip() == "split":
            split = val
        elif key.strip() == "start":
            start = val
        elif key.strip() == "end":
            end = val

    source = PDDocument.load(src_path)
    splitter = Splitter()
    try:
        # Same setter order as PDFSplit / the Java probe: start, end, split.
        if start is not None:
            splitter.set_start_page(start)
        if end is not None:
            splitter.set_end_page(end)
        if split is not None:
            splitter.set_split_at_page(split)
        parts = splitter.split(source)
    except ValueError as exc:
        source.close()
        return "err " + type(exc).__name__

    try:
        counts = [part.get_number_of_pages() for part in parts]
        mb = "-"
        rot = "-"
        if parts and parts[0].get_number_of_pages() > 0:
            first = parts[0].get_page(0)
            rect = first.get_media_box()
            mb = (
                f"{round(rect.get_lower_left_x())},"
                f"{round(rect.get_lower_left_y())},"
                f"{round(rect.get_width())},"
                f"{round(rect.get_height())}"
            )
            rot = str(first.get_rotation())
        pages = ",".join(str(c) for c in counts)
        return f"ok count={len(parts)} pages={pages} firstmb={mb} firstrot={rot}"
    finally:
        for part in parts:
            part.close()
        source.close()


def _verdict(fingerprint: str) -> str:
    """Collapse a rejection to the verdict ``err`` (language-idiomatic
    exception-class difference is a documented non-bug); leave a successful
    fingerprint verbatim so the structural facts are still compared exactly."""
    return "err" if fingerprint.startswith("err") else fingerprint


# Each case: (id, builder, build_kwargs, config). The builder + kwargs make the
# source document; config is the setter grammar driven through both engines.
_CASES = [
    # ---- setSplitAtPage granularity on a 3-page doc ----
    ("3p_split1", _plain, {"n_pages": 3}, "split=1"),
    ("3p_split2", _plain, {"n_pages": 3}, "split=2"),
    ("3p_split3", _plain, {"n_pages": 3}, "split=3"),
    ("3p_split_oversize", _plain, {"n_pages": 3}, "split=99"),
    ("3p_split0_invalid", _plain, {"n_pages": 3}, "split=0"),
    # ---- 7-page doc, interior + boundary intervals ----
    ("7p_split3", _plain, {"n_pages": 7}, "split=3"),
    ("7p_split4", _plain, {"n_pages": 7}, "split=4"),
    ("7p_split2_start2", _plain, {"n_pages": 7}, "split=2;start=2"),
    ("7p_range_split2", _plain, {"n_pages": 7}, "start=2;end=6;split=2"),
    ("7p_start7_lastpage", _plain, {"n_pages": 7}, "start=7"),
    ("7p_start1_end1", _plain, {"n_pages": 7}, "start=1;end=1"),
    # ---- single-page doc ----
    ("1p_split1", _plain, {"n_pages": 1}, "split=1"),
    ("1p_split2_oversize", _plain, {"n_pages": 1}, "split=2"),
    # ---- 2-page doc ----
    ("2p_split1", _plain, {"n_pages": 2}, "split=1"),
    ("2p_split5_oversize", _plain, {"n_pages": 2}, "split=5"),
    # ---- start/end bounds on a 5-page doc ----
    ("5p_range_2_4", _plain, {"n_pages": 5}, "start=2;end=4"),
    ("5p_range_2_4_split1", _plain, {"n_pages": 5}, "start=2;end=4;split=1"),
    ("5p_start3", _plain, {"n_pages": 5}, "start=3"),
    ("5p_end2", _plain, {"n_pages": 5}, "end=2"),
    ("5p_start_past_end", _plain, {"n_pages": 5}, "start=10"),
    ("5p_end_past_count", _plain, {"n_pages": 5}, "end=10"),
    ("5p_start_gt_end_invalid", _plain, {"n_pages": 5}, "start=4;end=2"),
    ("5p_default", _plain, {"n_pages": 5}, ""),
    # ---- rotation survival ----
    ("3p_rot90_split2", _plain, {"n_pages": 3, "rotate": 90}, "split=2"),
    ("4p_rot270_split2", _plain, {"n_pages": 4, "rotate": 270}, "split=2"),
    # ---- inherited /MediaBox + /Rotate ----
    ("inherit_split1", _inherited_geometry, {}, "split=1"),
    ("inherit_split2", _inherited_geometry, {}, "split=2"),
    ("inherit_range", _inherited_geometry, {}, "start=2;end=3"),
    # ---- zero-page source ----
    ("zero_split1", _zero_page, {}, "split=1"),
    ("zero_default", _zero_page, {}, ""),
]


@requires_oracle
@pytest.mark.parametrize(
    ("case_id", "builder", "build_kwargs", "config"),
    _CASES,
    ids=[c[0] for c in _CASES],
)
def test_splitter_config_fuzz_matches_pdfbox(
    case_id: str,
    builder,  # noqa: ANN001 - builder callables differ in signature
    build_kwargs: dict,
    config: str,
    tmp_path: Path,
) -> None:
    src = builder(tmp_path, **build_kwargs)

    java_fp = run_probe_text("SplitterFuzzProbe", str(src), config).strip()
    py_fp = _split_py(src, config)

    # Rejection cases: both engines must reject (verdict ``err``); the
    # exception-class string differs by language and is a documented non-bug.
    if java_fp.startswith("err") or py_fp.startswith("err"):
        assert _verdict(java_fp) == _verdict(py_fp) == "err", (
            f"rejection divergence for {case_id}:\n"
            f"  PDFBox:   {java_fp}\n  pypdfbox: {py_fp}"
        )
        return

    # Success cases: the full structural fingerprint must match exactly —
    # result count, per-result page counts, and the first result's first-page
    # MediaBox + Rotate (inherited-attribute survival).
    assert py_fp == java_fp, (
        f"split config fingerprint divergence for {case_id}:\n"
        f"  PDFBox:   {java_fp}\n  pypdfbox: {py_fp}"
    )
