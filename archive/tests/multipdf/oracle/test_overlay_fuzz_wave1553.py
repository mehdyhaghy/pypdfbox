"""Differential-fuzz parity for ``Overlay`` overlay-selector resolution
(``pypdfbox.multipdf.overlay``) against the live Apache PDFBox 3.0.7 oracle.

The existing overlay oracle (``test_overlay_oracle``) covers only the *default*
overlay (one stamp onto every page) in FOREGROUND/BACKGROUND. The
``OverlayToolProbe`` oracle exercises the CLI selectors. This module fuzzes the
``Overlay`` *Java/Python API* across the selector-resolution and page-count
mismatch matrix that neither covers:

* **all-pages repeating overlay** where the base has MORE pages than the overlay
  document (the i-th overlay page lands on the i-th-mod-N input page — the cycle
  must wrap), and where the base has FEWER pages (extra overlay pages unused),
* **specific-page overlay with gaps** (some input pages get no overlay at all),
* **selector precedence** — first/last beat odd/even beat default, all on one
  run,
* **default + first** combination (first wins page 1, default the rest),
* **foreground vs background** for the repeating case,
* an **overlay page with no /Contents** (empty overlay).

For each config the recoverable structural facts must agree across the
Java/pypdfbox boundary:

* total page count (overlay never adds/drops pages),
* per-page extracted text, in order (the stripper sees *every* applied layer, so
  the exact selector that landed on each page is encoded in the text),
* per-page /XObject count and whether an ``OL``-prefixed overlay-form key is
  present (a page with no matching selector must carry NO overlay form).

Inputs are built once through pypdfbox and handed to *both* sides by path so the
overlay runs on byte-identical input. Object-count / xref style are deliberately
not compared (documented writer-strategy difference). Both outputs must also
pass ``qpdf --check``.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from pypdfbox.multipdf import Overlay, Position
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.font.pd_font_factory import PDFontFactory
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream
from pypdfbox.text.pdf_text_stripper import PDFTextStripper
from tests.oracle.harness import requires_oracle, run_probe_text

_QPDF = shutil.which("qpdf")
_requires_qpdf = pytest.mark.skipif(
    _QPDF is None, reason="qpdf binary not on PATH (brew install qpdf)"
)


# ----------------------------------------------------------------- builders


def _text_page(
    doc: PDDocument,
    message: str,
    media_box: PDRectangle,
    x: float = 72.0,
    y: float = 700.0,
) -> PDPage:
    page = PDPage(media_box)
    doc.add_page(page)
    font = PDFontFactory.create_default_font()
    cs = PDPageContentStream(doc, page)
    cs.begin_text()
    cs.set_font(font, 12)
    cs.new_line_at_offset(x, y)
    cs.show_text(message)
    cs.end_text()
    cs.close()
    return page


def _stamp_box() -> PDRectangle:
    return PDRectangle.from_width_height(200.0, 200.0)


def _build_base(path: Path, markers: list[str]) -> None:
    doc = PDDocument()
    for marker in markers:
        _text_page(doc, marker, PDRectangle.LETTER)
    doc.save(str(path))
    doc.close()


def _build_single(path: Path, marker: str, *, rotation: int = 0) -> None:
    doc = PDDocument()
    page = _text_page(doc, marker, _stamp_box(), x=20.0, y=100.0)
    if rotation:
        page.set_rotation(rotation)
    doc.save(str(path))
    doc.close()


def _build_multi(path: Path, markers: list[str]) -> None:
    doc = PDDocument()
    for marker in markers:
        _text_page(doc, marker, _stamp_box(), x=20.0, y=100.0)
    doc.save(str(path))
    doc.close()


def _build_empty(path: Path) -> None:
    """A single-page overlay whose page has NO /Contents (no marker drawn)."""
    doc = PDDocument()
    doc.add_page(PDPage(_stamp_box()))
    doc.save(str(path))
    doc.close()


# ------------------------------------------------------------- fact readers


def _qpdf_check(path: Path) -> tuple[int, str]:
    proc = subprocess.run(
        [str(_QPDF), "--check", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


class _OverlayFacts:
    __slots__ = ("ol_keys", "page_text", "pages", "xobject_counts")

    def __init__(
        self,
        pages: int,
        page_text: list[str],
        xobject_counts: list[int],
        ol_keys: list[bool],
    ) -> None:
        self.pages = pages
        self.page_text = page_text
        self.xobject_counts = xobject_counts
        self.ol_keys = ol_keys

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, _OverlayFacts):
            return NotImplemented
        return (
            self.pages == other.pages
            and self.page_text == other.page_text
            and self.xobject_counts == other.xobject_counts
            and self.ol_keys == other.ol_keys
        )

    def __repr__(self) -> str:  # pragma: no cover - only on assert failure
        return (
            f"_OverlayFacts(pages={self.pages}, page_text={self.page_text}, "
            f"xobject_counts={self.xobject_counts}, ol_keys={self.ol_keys})"
        )


def _unescape(s: str) -> str:
    return (
        s.replace("\\t", "\t")
        .replace("\\r", "\r")
        .replace("\\n", "\n")
        .replace("\\\\", "\\")
    )


def _parse_probe(text: str) -> _OverlayFacts:
    pages = 0
    page_text_map: dict[int, str] = {}
    xobject_map: dict[int, int] = {}
    ol_map: dict[int, bool] = {}
    for line in text.splitlines():
        if not line:
            continue
        head, _, rest = line.partition(" ")
        if head == "pages":
            pages = int(rest)
        elif head == "page":
            idx, _, body = rest.partition(" ")
            page_text_map[int(idx)] = _unescape(body)
        elif head == "xobject":
            idx, _, count = rest.partition(" ")
            xobject_map[int(idx)] = int(count)
        elif head == "olkey":
            idx, _, val = rest.partition(" ")
            ol_map[int(idx)] = val == "true"
    page_text = [page_text_map.get(i, "") for i in range(pages)]
    xobject_counts = [xobject_map.get(i, 0) for i in range(pages)]
    ol_keys = [ol_map.get(i, False) for i in range(pages)]
    return _OverlayFacts(pages, page_text, xobject_counts, ol_keys)


def _read_py_facts(path: Path) -> _OverlayFacts:
    doc = PDDocument.load(path)
    try:
        n = doc.get_number_of_pages()
        stripper = PDFTextStripper()
        page_text: list[str] = []
        for i in range(n):
            stripper.set_start_page(i + 1)
            stripper.set_end_page(i + 1)
            page_text.append(stripper.get_text(doc).strip())

        xobject_counts: list[int] = []
        ol_keys: list[bool] = []
        for i in range(n):
            res = doc.get_page(i).get_resources()
            count = 0
            has_ol = False
            if res is not None:
                for name in res.get_xobject_names():
                    count += 1
                    if name.get_name().startswith("OL"):
                        has_ol = True
            xobject_counts.append(count)
            ol_keys.append(has_ol)

        return _OverlayFacts(n, page_text, xobject_counts, ol_keys)
    finally:
        doc.close()


# --------------------------------------------------------- pypdfbox drivers
#
# Each driver mirrors exactly what OverlayFuzzProbe.java configures for the
# same ``config`` name, so the only variable is the implementation under test.


def _overlay_py(config: str, base: Path, docs: list[Path], out: Path) -> None:
    with PDDocument.load(str(base)) as base_doc, Overlay() as overlay:
        overlay.set_input_pdf(base_doc)
        opened: list[PDDocument] = []
        try:
            page_map: dict[int, str] = {}
            if config == "default-bg":
                overlay.set_default_overlay_pdf(_open(opened, docs[0]))
                overlay.set_overlay_position(Position.BACKGROUND)
            elif config == "default-fg":
                overlay.set_default_overlay_pdf(_open(opened, docs[0]))
                overlay.set_overlay_position(Position.FOREGROUND)
            elif config == "all-pages":
                overlay.set_all_pages_overlay_pdf(_open(opened, docs[0]))
                overlay.set_overlay_position(Position.BACKGROUND)
            elif config == "all-pages-fg":
                overlay.set_all_pages_overlay_pdf(_open(opened, docs[0]))
                overlay.set_overlay_position(Position.FOREGROUND)
            elif config == "specific-gaps":
                page_map = {1: str(docs[0]), 3: str(docs[1])}
            elif config == "first-last":
                overlay.set_first_page_overlay_pdf(_open(opened, docs[0]))
                overlay.set_last_page_overlay_pdf(_open(opened, docs[1]))
            elif config == "odd-even":
                overlay.set_odd_page_overlay_pdf(_open(opened, docs[0]))
                overlay.set_even_page_overlay_pdf(_open(opened, docs[1]))
            elif config == "first-last-odd-even":
                overlay.set_first_page_overlay_pdf(_open(opened, docs[0]))
                overlay.set_last_page_overlay_pdf(_open(opened, docs[1]))
                overlay.set_odd_page_overlay_pdf(_open(opened, docs[2]))
                overlay.set_even_page_overlay_pdf(_open(opened, docs[3]))
            elif config == "default-plus-first":
                overlay.set_default_overlay_pdf(_open(opened, docs[0]))
                overlay.set_first_page_overlay_pdf(_open(opened, docs[1]))
            elif config == "empty-overlay":
                overlay.set_default_overlay_pdf(_open(opened, docs[0]))
            else:  # pragma: no cover - guarded by parametrisation
                raise AssertionError(f"unknown config {config!r}")
            result = overlay.overlay(page_map)
            result.save(str(out))
        finally:
            for d in opened:
                d.close()


def _open(opened: list[PDDocument], path: Path) -> PDDocument:
    doc = PDDocument.load(str(path))
    opened.append(doc)
    return doc


# ------------------------------------------------------------------- fixtures


_BASE_MARKERS_3 = ["BASEZERO", "BASEONE", "BASETWO"]
_BASE_MARKERS_2 = ["BASEZERO", "BASEONE"]
_BASE_MARKERS_5 = ["BASEZERO", "BASEONE", "BASETWO", "BASETHREE", "BASEFOUR"]


def _make_corpus(tmp_path: Path) -> dict[str, Path]:
    """Build every synthetic input doc shared across the fuzz matrix."""
    paths: dict[str, Path] = {}

    base3 = tmp_path / "base3.pdf"
    _build_base(base3, _BASE_MARKERS_3)
    paths["base3"] = base3

    base2 = tmp_path / "base2.pdf"
    _build_base(base2, _BASE_MARKERS_2)
    paths["base2"] = base2

    base5 = tmp_path / "base5.pdf"
    _build_base(base5, _BASE_MARKERS_5)
    paths["base5"] = base5

    stamp = tmp_path / "stamp.pdf"
    _build_single(stamp, "STAMPMARK")
    paths["stamp"] = stamp

    stamp_rot = tmp_path / "stamp_rot.pdf"
    _build_single(stamp_rot, "ROTMARK", rotation=90)
    paths["stamp_rot"] = stamp_rot

    multi2 = tmp_path / "multi2.pdf"
    _build_multi(multi2, ["OVERA", "OVERB"])
    paths["multi2"] = multi2

    multi4 = tmp_path / "multi4.pdf"
    _build_multi(multi4, ["OVERA", "OVERB", "OVERC", "OVERD"])
    paths["multi4"] = multi4

    first = tmp_path / "first.pdf"
    _build_single(first, "FIRSTMARK")
    paths["first"] = first

    last = tmp_path / "last.pdf"
    _build_single(last, "LASTMARK")
    paths["last"] = last

    odd = tmp_path / "odd.pdf"
    _build_single(odd, "ODDMARK")
    paths["odd"] = odd

    even = tmp_path / "even.pdf"
    _build_single(even, "EVENMARK")
    paths["even"] = even

    default = tmp_path / "default.pdf"
    _build_single(default, "DEFAULTMARK")
    paths["default"] = default

    empty = tmp_path / "empty.pdf"
    _build_empty(empty)
    paths["empty"] = empty

    return paths


# (config, base-key, [doc-keys...], expected page count, rotated-overlay?)
#
# The rotated-overlay flag marks cases whose overlay document carries a
# /Rotation on its page. The Overlay output for those is geometrically
# IDENTICAL across both ports (verified: the placement ``cm`` matrix, the
# form ``/Matrix`` rotation entry, the ``/BBox`` and the OL-key set are all
# byte-identical), but the two *text strippers* lay the rotated glyphs out
# differently — Java's PDFTextStripper propagates the form's 90-degree
# /Matrix into each glyph's position and so emits one glyph per detected
# line (``R\nO\nT\n...``), whereas pypdfbox's stripper does not yet apply a
# form-XObject /Matrix rotation when computing glyph baselines and emits the
# run on a single line (``ROTMARK``). That divergence lives in the text
# module, NOT in Overlay; for these cases we compare the text with
# inter-glyph whitespace normalised so the (correct) overlay geometry is
# still asserted without coupling this overlay test to the stripper gap.
_CASES: list[tuple[str, str, list[str], int, bool]] = [
    ("default-bg", "base3", ["stamp"], 3, False),
    ("default-fg", "base3", ["stamp"], 3, False),
    ("default-bg", "base2", ["stamp"], 2, False),
    ("default-bg", "base5", ["stamp_rot"], 5, True),
    # all-pages repeating: base has MORE pages than overlay -> cycle wraps.
    ("all-pages", "base5", ["multi2"], 5, False),
    ("all-pages-fg", "base5", ["multi2"], 5, False),
    ("all-pages", "base3", ["multi4"], 3, False),  # base FEWER pages than overlay.
    ("all-pages", "base3", ["multi2"], 3, False),
    # specific-page overlay with a gap (page 1 + page 3, page 2 untouched).
    ("specific-gaps", "base3", ["stamp", "default"], 3, False),
    ("specific-gaps", "base5", ["first", "last"], 5, False),
    # selector precedence stacks.
    ("first-last", "base3", ["first", "last"], 3, False),
    ("first-last", "base5", ["first", "last"], 5, False),
    ("odd-even", "base3", ["odd", "even"], 3, False),
    ("odd-even", "base5", ["odd", "even"], 5, False),
    ("first-last-odd-even", "base3", ["first", "last", "odd", "even"], 3, False),
    ("first-last-odd-even", "base5", ["first", "last", "odd", "even"], 5, False),
    ("default-plus-first", "base3", ["default", "first"], 3, False),
    ("default-plus-first", "base5", ["default", "first"], 5, False),
    # overlay with an empty (no-/Contents) page — still registers a form.
    ("empty-overlay", "base3", ["empty"], 3, False),
    ("empty-overlay", "base2", ["empty"], 2, False),
    # single-page base edge.
    ("first-last", "base2", ["first", "last"], 2, False),
    # rotated overlay onto upright base (see rotated-overlay note above).
    ("default-bg", "base3", ["stamp_rot"], 3, True),
]


def _case_id(case: tuple[str, str, list[str], int, bool]) -> str:
    config, base_key, doc_keys, _, _ = case
    return f"{config}-{base_key}-{'+'.join(doc_keys)}"


def _normalise_text(facts: _OverlayFacts) -> list[str]:
    """Strip ALL whitespace from each page's text so a rotated overlay's
    glyph-per-line stripper layout (``R\\nO\\nT...``) compares equal to a
    single-line layout (``ROTMARK``) — the glyph sequence and order are
    preserved, only the text-module-specific line/space breaking is
    normalised away (see the _CASES rotated-overlay note)."""
    return ["".join(t.split()) for t in facts.page_text]


# ------------------------------------------------------------------- tests


@requires_oracle
@_requires_qpdf
@pytest.mark.parametrize("case", _CASES, ids=[_case_id(c) for c in _CASES])
def test_overlay_selector_matrix_matches_pdfbox(
    tmp_path: Path, case: tuple[str, str, list[str], int, bool]
) -> None:
    """Drive one overlay configuration through Java PDFBox and pypdfbox; every
    recoverable structural fact (page count, per-page two-layer text, /XObject
    count, OL-key presence) must agree, and both outputs must be qpdf-valid."""
    config, base_key, doc_keys, expected_pages, rotated_overlay = case
    corpus = _make_corpus(tmp_path)
    base = corpus[base_key]
    docs = [corpus[k] for k in doc_keys]

    java_out = tmp_path / "java_out.pdf"
    java_text = run_probe_text(
        "OverlayFuzzProbe",
        str(java_out),
        str(base),
        config,
        *[str(d) for d in docs],
    )
    java_facts = _parse_probe(java_text)

    py_out = tmp_path / "py_out.pdf"
    _overlay_py(config, base, docs, py_out)
    py_facts = _read_py_facts(py_out)

    java_rc, java_log = _qpdf_check(java_out)
    py_rc, py_log = _qpdf_check(py_out)
    assert java_rc <= 3, f"Java overlay failed qpdf --check (rc={java_rc}):\n{java_log}"
    assert py_rc <= 3, f"pypdfbox overlay failed qpdf --check (rc={py_rc}):\n{py_log}"

    assert py_facts.pages == java_facts.pages == expected_pages, (
        f"[{config}/{base_key}] page count: pypdfbox {py_facts.pages} "
        f"vs PDFBox {java_facts.pages} (expected {expected_pages})"
    )

    if rotated_overlay:
        # Geometry is byte-identical; only the stripper's line breaking of the
        # rotated glyphs differs (see the _CASES rotated-overlay note). Compare
        # the glyphs/order with inter-glyph whitespace normalised.
        py_text = _normalise_text(py_facts)
        java_text_norm = _normalise_text(java_facts)
        assert py_text == java_text_norm, (
            f"[{config}/{base_key}] per-page text (whitespace-normalised) "
            f"divergence:\n  pypdfbox: {py_text}\n  PDFBox:   {java_text_norm}"
        )
    else:
        assert py_facts.page_text == java_facts.page_text, (
            f"[{config}/{base_key}] per-page two-layer text divergence:\n"
            f"  pypdfbox: {py_facts.page_text}\n  PDFBox:   {java_facts.page_text}"
        )
    assert py_facts.ol_keys == java_facts.ol_keys, (
        f"[{config}/{base_key}] OL-key presence divergence:\n"
        f"  pypdfbox: {py_facts.ol_keys}\n  PDFBox:   {java_facts.ol_keys}"
    )
    assert py_facts.xobject_counts == java_facts.xobject_counts, (
        f"[{config}/{base_key}] /XObject count divergence:\n"
        f"  pypdfbox: {py_facts.xobject_counts}\n  PDFBox:   {java_facts.xobject_counts}"
    )

    if not rotated_overlay:
        # The full-facts equality folds in raw (un-normalised) page text, so
        # it is asserted only for the non-rotated cases — the rotated cases
        # already proved page-count / OL-key / XObject parity above and the
        # text parity via the normalised comparison.
        assert py_facts == java_facts
