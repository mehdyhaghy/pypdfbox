"""Live Apache PDFBox differential parity for gap-driven word-separator
insertion — the rule that a single space is inserted between two glyphs whose
horizontal gap exceeds a fraction of the space / average glyph width, with NO
space for a normal inter-letter gap, and exactly ONE space (never a run) for a
very wide gap.

The word break here is encoded purely by *positioning*: two separate ``Tj``
operators on the same baseline, the second re-anchored by a ``Td`` so the
inter-run gap is the only thing separating the words — there is no space glyph
(code 32) anywhere in the content stream. This isolates the gap → space
heuristic from the ``Tw`` / explicit-space machinery.

Each run is its own show-text operator, so the inter-run gap lands on a run
boundary that the lite per-run stripper observes identically to Java's
per-glyph stripper. The default word separator is overridden with the sentinel
``|W|`` (line separator ``|L|``) so the exact count of inserted breaks is
visible in the extracted string rather than blurred into ordinary whitespace.

Three gap regimes:

* **sub-threshold** — the words abut (tiny gap); no separator: ``ABCD``. At
  full parity (asserted positively).
* **supra-threshold** — a *mid-size* gap (here ~34pt at 24pt font, gap/space
  ratio ~5): Java inserts exactly one separator (``AB|W|CD``) because its
  threshold is space-glyph-width-relative (``gap > wordSpacing *
  spacingTolerance`` ≈ 3.3pt). The lite stripper's coarser ``font_size * 1.5``
  (~36pt) gap threshold does not fire, so it extracts ``ABCD``. This is the
  pre-existing, already-DEFERRED word-break-threshold calibration divergence
  (DEFERRED.md "word-break gap-threshold calibration", surfaced wave 1465 and
  also pinned in ``test_horiz_scaling_oracle.py``). Pinned strict-``xfail``
  here rather than weakened — recalibrating ``_is_word_break`` to PDFBox's
  wordSpacing-relative formula is a headline word-segmentation change spanning
  the whole ``getText`` suite. Same family as the per-run-granularity
  carve-outs.
* **very large** — a page-spanning gap (~204pt): clears even the coarse
  ``font_size * 1.5`` threshold, so both engines emit exactly one separator
  (``AB|W|CD``) — never a run of them. At full parity (asserted positively).

``@requires_oracle`` so it skips cleanly without Java + the jar.
Hand-written (not ported from upstream JUnit).
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from pypdfbox.cos import COSStream
from pypdfbox.pdmodel import PDDocument
from pypdfbox.pdmodel.common import PDRectangle
from pypdfbox.pdmodel.font import PDFontFactory, Standard14Fonts
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.text.pdf_text_stripper import PDFTextStripper
from tests.oracle.harness import requires_oracle, run_probe_text

_PROBE = "WordGapSpaceProbe"

# 24pt Helvetica: "AB" advances ~32pt (A=B=0.667em*24). Two Tj runs on one
# baseline; the second is placed by an absolute Td so the only thing between
# the words is the horizontal gap — no space glyph in the stream.
#
# (a) sub-threshold: second run starts right where the first ends (~32pt),
#     a normal inter-letter step -> NO separator.
_GAP_NONE = b"BT /F1 24 Tf 20 150 Td (AB) Tj 33 0 Td (CD) Tj ET"
# (b) supra-threshold: a clear ~24pt gap beyond the first run's right edge
#     -> exactly ONE separator.
_GAP_ONE = b"BT /F1 24 Tf 20 150 Td (AB) Tj 60 0 Td (CD) Tj ET"
# (c) very large: a ~200pt page-spanning jump -> still exactly ONE separator,
#     never a run of them.
_GAP_HUGE = b"BT /F1 24 Tf 20 150 Td (AB) Tj 230 0 Td (CD) Tj ET"


def _build_pdf(content: bytes, path: str) -> None:
    """Build a one-page PDF whose page content is exactly ``content``.

    The ``/F1`` token in ``content`` is rewritten to whatever key the page
    resources actually allocate for the embedded Helvetica font.
    """
    doc = PDDocument()
    try:
        page = PDPage(PDRectangle(0, 0, 500, 200))
        doc.add_page(page)
        font = PDFontFactory.create_default_font(
            Standard14Fonts.FontName.HELVETICA.value
        )
        resources = page.get_resources()
        font_key = resources.add(font)
        page.set_resources(resources)
        rewritten = content.replace(
            b"/F1", b"/" + font_key.get_name().encode("ascii")
        )
        stream = COSStream()
        with stream.create_output_stream() as out:
            out.write(rewritten)
        page.set_contents(stream)
        doc.save(path)
    finally:
        doc.close()


def _java(path: str) -> str:
    out = run_probe_text(_PROBE, path)
    return out.split("<<<TEXT\n", 1)[1].split("TEXT>>>\n", 1)[0]


def _py(path: str) -> str:
    doc = PDDocument.load(path)
    try:
        stripper = PDFTextStripper()
        stripper.set_sort_by_position(True)
        stripper.set_word_separator("|W|")
        stripper.set_line_separator("|L|")
        return stripper.get_text(doc)
    finally:
        doc.close()


def _roundtrip(content: bytes) -> tuple[str, str]:
    with tempfile.TemporaryDirectory() as td:
        path = str(Path(td) / "case.pdf")
        _build_pdf(content, path)
        return _java(path), _py(path)


# ---------------------------------------------------------------------------
# Sub-threshold (abutting words) and very-large (page-spanning) gaps are at
# full parity: the coarse lite threshold classifies both identically to Java.
# ---------------------------------------------------------------------------


@requires_oracle
@pytest.mark.parametrize(
    "content",
    [_GAP_NONE, _GAP_HUGE],
    ids=["sub_threshold", "very_large"],
)
def test_gap_space_insertion_matches_pdfbox(content: bytes) -> None:
    java_text, py_text = _roundtrip(content)
    assert py_text == java_text


@requires_oracle
def test_sub_threshold_gap_emits_no_separator() -> None:
    java_text, py_text = _roundtrip(_GAP_NONE)
    assert "|W|" not in java_text
    assert py_text == java_text


@requires_oracle
def test_very_large_gap_emits_exactly_one_separator() -> None:
    java_text, py_text = _roundtrip(_GAP_HUGE)
    # A page-spanning gap inserts exactly one word separator — never a run of
    # them, no matter how large the gap. Both engines agree.
    assert java_text.count("|W|") == 1
    assert py_text == java_text


# ---------------------------------------------------------------------------
# Mid-size gap — the documented, already-DEFERRED word-break-threshold
# calibration divergence. Java breaks (space-width-relative threshold); the
# lite stripper's font_size*1.5 (~36pt) threshold misses a ~34pt gap. Pinned
# strict-xfail so a future wordSpacing-relative recalibration flips it green.
# ---------------------------------------------------------------------------


@requires_oracle
@pytest.mark.xfail(
    reason="word-break gap-threshold calibration (DEFERRED.md, surfaced wave "
    "1465): for a mid-size positioning gap (~34pt at 24pt font, gap/space "
    "ratio ~5) Java inserts a word separator because its threshold is "
    "space-glyph-width-relative (gap > wordSpacing * spacingTolerance ≈ "
    "3.3pt), but the lite stripper's coarser font_size*1.5 (~36pt) gap "
    "threshold does not fire, so it extracts 'ABCD' not 'AB|W|CD'. "
    "Recalibrating _is_word_break to PDFBox's wordSpacing-relative formula is "
    "a headline word-segmentation change spanning the whole getText suite — "
    "deferred. Same family as the per-run-granularity carve-outs and the "
    "test_horiz_scaling_oracle.py mid-size-TJ-jump xfail.",
    strict=True,
)
def test_mid_size_gap_word_break_matches_pdfbox() -> None:
    java_text, py_text = _roundtrip(_GAP_ONE)
    assert java_text.count("|W|") == 1
    assert py_text == java_text
