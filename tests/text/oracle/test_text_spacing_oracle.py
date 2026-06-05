"""Live Apache PDFBox differential parity tests for the text-state spacing
parameters that shift glyph X positions and govern word-break insertion:

* ``Tc`` — character spacing (added to every glyph advance),
* ``Tw`` — word spacing (added to the advance of the single-byte code 32
  *only* — PDF 1.7 §9.3.3),
* ``Tz`` — horizontal scaling (a percentage that compresses/stretches X),
* ``Ts`` — text rise (a vertical baseline shift; superscripts),
* the ``TJ`` array numeric adjustments (thousandths of an em, subtracted
  from the X cursor; a large-enough forward jump makes the stripper insert
  a word separator between the two adjacent strings).

The :class:`TextSpacingProbe` Java probe subclasses ``PDFTextStripper``,
emits the full extracted string (so whitespace / word breaks are recovered
exactly) and one canonical ``unicode \t xDirAdj \t yDirAdj \t widthDirAdj``
line per glyph in reading order.

Granularity reconciliation (the documented lite-port carve-out — see
``test_text_position_oracle.py`` and ``CHANGES.md``): Apache PDFBox emits
one ``TextPosition`` *per glyph* and advances the X cursor by each glyph's
true width plus ``Tc`` (and ``Tw`` on code 32); pypdfbox's lite stripper
emits one ``TextPosition`` per *show-text run* (a ``Tj`` string or a single
``TJ`` array element) and advances by the font's *average* glyph width. So:

* **String / word-break parity is the headline metric.** Where the word
  break falls at a *run boundary* — between two ``TJ`` array strings, or
  between separate ``Tj`` operators — the lite stripper sees the same
  inter-run gap Java does and inserts (or omits) the separator identically.
  ``Tw`` / ``Tz`` / ``Ts`` and the ``TJ`` adjustment magnitude/sign are all
  exercised this way and match Java's extracted string exactly.
* **``Tc`` inside a single run** is the one documented divergence: Java
  treats the Tc-widened gap between two glyphs of one ``Tj`` string as a
  per-glyph word break, but the lite stripper holds the whole string in one
  ``TextPosition`` and never re-examines intra-run glyph gaps. That case is
  ``xfail``-ed with a precise reason rather than weakened — it is the
  per-glyph-granularity carve-out, not a Tc sign/scale bug.
* **Per-glyph X cannot match** (per-run vs per-glyph granularity + the
  average-advance width estimate). We instead assert that the *first run's*
  origin X — re-anchored by ``Td`` — matches Java's first glyph X exactly,
  and document the inter-run drift.

Decorated ``@requires_oracle`` so it skips cleanly without Java + the jar.
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
from pypdfbox.text.text_position import TextPosition
from tests.oracle.harness import requires_oracle, run_probe_text

_PROBE = "TextSpacingProbe"
_COORD_EPS = 0.5


# ---------------------------------------------------------------------------
# Fixtures: one-page PDFs whose content stream is exactly the bytes below,
# built with a single Helvetica-class font (registered as the page's first
# /Font resource; the ``/F1`` placeholder is rewritten to the real key).
# ---------------------------------------------------------------------------

# (a) large Tc — char spacing of 10pt widens every glyph gap.
_TC = b"BT /F1 24 Tf 10 Tc 20 150 Td (AB CD) Tj ET"
# (b) large Tw — word spacing of 30pt; PDF 1.7 §9.3.3 says it applies only
#     to the single-byte space (code 32), never to A/B/C/D.
_TW = b"BT /F1 24 Tf 30 Tw 20 150 Td (AB CD) Tj ET"
# (c) Tz 50 — horizontal compression to 50%.
_TZ = b"BT /F1 24 Tf 50 Tz 20 150 Td (AB CD) Tj ET"
# (d) Ts — text rise; CD is raised 8pt (superscript), then reset.
_TS = b"BT /F1 24 Tf 20 150 Td (AB) Tj 8 Ts (CD) Tj 0 Ts (EF) Tj ET"
# (e) TJ large negative adjustment (-2000 = 48pt forward) -> word break.
_TJ_BREAK = b"BT /F1 24 Tf 20 150 Td [(AB) -2000 (CD)] TJ ET"
# (e2) TJ small negative adjustment (-120) -> below threshold, no break.
_TJ_NOBREAK = b"BT /F1 24 Tf 20 150 Td [(AB) -120 (CD)] TJ ET"
# (e3) TJ positive adjustment (+200 = move back) -> no break.
_TJ_POS = b"BT /F1 24 Tf 20 150 Td [(AB) 200 (CD)] TJ ET"


def _build_pdf(content: bytes, path: str) -> None:
    """Build a one-page PDF whose page content is exactly ``content``.

    The ``/F1`` token in ``content`` is rewritten to whatever key the page
    resources actually allocate for the embedded Helvetica font.
    """
    doc = PDDocument()
    try:
        page = PDPage(PDRectangle(0, 0, 400, 200))
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


class _Glyph:
    """One parsed glyph line from the probe's GLYPHS section."""

    __slots__ = ("unicode", "x", "y", "width")

    def __init__(self, fields: list[str]) -> None:
        self.unicode = fields[0]
        self.x = float(fields[1])
        self.y = float(fields[2])
        self.width = float(fields[3])


def _java(path: str) -> tuple[str, list[_Glyph]]:
    """Run the probe; return ``(extracted_text, glyphs)``."""
    out = run_probe_text(_PROBE, path)
    # The probe frames the extracted text as ``<<<TEXT\n{text}TEXT>>>\n`` —
    # split on the bare sentinels so the extracted text (including its own
    # trailing newline / page separator) is preserved byte-for-byte.
    text_part = out.split("<<<TEXT\n", 1)[1].split("TEXT>>>\n", 1)[0]
    glyph_part = out.split("<<<GLYPHS\n", 1)[1].split("GLYPHS>>>", 1)[0]
    glyphs: list[_Glyph] = []
    for line in glyph_part.splitlines():
        if not line:
            continue
        fields = line.split("\t")
        if len(fields) != 4:
            continue
        glyphs.append(_Glyph(fields))
    return text_part, glyphs


def _py(path: str) -> tuple[str, list[TextPosition], float]:
    """Extract with pypdfbox; return ``(text, runs, page_height)``.

    The document is closed in a ``finally`` so a Windows file lock is
    always released.
    """
    captured: list[TextPosition] = []

    class _Capture(PDFTextStripper):
        def write_string(self, text, text_positions, sink=None):  # type: ignore[override]
            captured.extend(text_positions)
            return super().write_string(text, text_positions, sink)

    doc = PDDocument.load(path)
    try:
        page = doc.get_page(0)
        ph = page.get_media_box().get_height()
        stripper = _Capture()
        stripper.set_sort_by_position(True)
        text = stripper.get_text(doc)
        return text, captured, ph
    finally:
        doc.close()


def _roundtrip(content: bytes) -> tuple[str, list[_Glyph], str, list[TextPosition], float]:
    """Build the PDF, run both Java and pypdfbox over it."""
    with tempfile.TemporaryDirectory() as td:
        path = str(Path(td) / "case.pdf")
        _build_pdf(content, path)
        java_text, java_glyphs = _java(path)
        py_text, py_runs, ph = _py(path)
    return java_text, java_glyphs, py_text, py_runs, ph


# ---------------------------------------------------------------------------
# String / word-break parity — the headline metric. Each of Tw / Tz / Ts and
# the three TJ-adjustment magnitudes must extract the exact same string as
# Java, because the (non-)word-break those parameters govern lands on a run
# boundary the lite stripper observes identically.
# ---------------------------------------------------------------------------


@requires_oracle
@pytest.mark.parametrize(
    "content",
    [_TW, _TZ, _TS, _TJ_BREAK, _TJ_NOBREAK, _TJ_POS],
    ids=["tw", "tz", "ts", "tj_break", "tj_nobreak", "tj_pos"],
)
def test_extracted_string_matches_pdfbox(content: bytes) -> None:
    java_text, _java_glyphs, py_text, _py_runs, _ph = _roundtrip(content)
    assert py_text == java_text


# ---------------------------------------------------------------------------
# Tw applies ONLY to the single-byte code 32 (PDF 1.7 §9.3.3). The probe's
# per-glyph X stream proves it: with Tw=30 the gap *after* the space glyph
# (space -> C) is widened by ~30pt while the A->B and C->D inter-glyph gaps
# are untouched. pypdfbox does not over-apply Tw to A/B/C/D — its extracted
# string is identical to the no-Tw layout's word structure ("AB CD").
# ---------------------------------------------------------------------------


@requires_oracle
def test_word_spacing_affects_only_code_32() -> None:
    java_text, java_glyphs, py_text, _py_runs, _ph = _roundtrip(_TW)
    # The string parity already pins that Tw did not spuriously split A/B
    # or C/D into separate words.
    assert py_text == java_text == "AB CD\n"

    by_char = {g.unicode: g for g in java_glyphs}
    a, b = by_char["A"], by_char["B"]
    space, c, d = by_char[" "], by_char["C"], by_char["D"]
    # Inter-glyph advances inside a word are the bare glyph widths (no Tw).
    ab_gap = b.x - a.x
    cd_gap = d.x - c.x
    assert ab_gap == pytest.approx(a.width, abs=_COORD_EPS)
    assert cd_gap == pytest.approx(c.width, abs=_COORD_EPS)
    # The advance consumed by the space glyph itself carries the +30pt Tw,
    # so the space->C gap is far larger than a bare space width.
    space_to_c = c.x - space.x
    assert space_to_c > space.width + 20.0
    # And Tw did NOT leak onto the B->space transition (that gap is just B's
    # width, not B's width + 30).
    b_to_space = space.x - b.x
    assert b_to_space == pytest.approx(b.width, abs=_COORD_EPS)


# ---------------------------------------------------------------------------
# TJ word-break threshold — sign + scale parity. A -2000 (48pt forward) jump
# crosses the separator threshold in both engines; -120 and +200 do not.
# ---------------------------------------------------------------------------


@requires_oracle
def test_tj_large_negative_inserts_word_break() -> None:
    java_text, _jg, py_text, py_runs, _ph = _roundtrip(_TJ_BREAK)
    assert py_text == java_text == "AB CD\n"
    # The TJ split is a genuine run boundary in the lite port (two runs).
    assert [r.text for r in py_runs] == ["AB", "CD"]


@requires_oracle
@pytest.mark.parametrize(
    "content", [_TJ_NOBREAK, _TJ_POS], ids=["small_negative", "positive"]
)
def test_tj_subthreshold_adjustment_no_word_break(content: bytes) -> None:
    java_text, _jg, py_text, _pr, _ph = _roundtrip(content)
    assert py_text == java_text == "ABCD\n"


# ---------------------------------------------------------------------------
# Run-origin X parity. Per-glyph X can't match (per-run granularity +
# average-advance width), but the first run's origin is re-anchored by Td and
# matches Java's first glyph X exactly across every spacing parameter.
# ---------------------------------------------------------------------------


@requires_oracle
@pytest.mark.parametrize(
    "content",
    [_TC, _TW, _TZ, _TS, _TJ_BREAK, _TJ_NOBREAK, _TJ_POS],
    ids=["tc", "tw", "tz", "ts", "tj_break", "tj_nobreak", "tj_pos"],
)
def test_first_run_origin_x_matches_pdfbox(content: bytes) -> None:
    _jt, java_glyphs, _pt, py_runs, ph = _roundtrip(content)
    assert java_glyphs and py_runs
    first_glyph = java_glyphs[0]
    first_run = py_runs[0]
    assert first_run.x == pytest.approx(first_glyph.x, abs=_COORD_EPS)
    # Y origin: pypdfbox keeps PDF y-up (lower-left); Java's getYDirAdj is
    # measured from the page top. They relate by java_y == page_height - py.y
    # on an unrotated page. (Ts/text-rise is applied per-glyph by Java but
    # not by the lite per-run stripper — the *first* glyph here is on the
    # baseline in every case, so the origin still reconciles.)
    assert (ph - first_run.y) == pytest.approx(first_glyph.y, abs=_COORD_EPS)


# ---------------------------------------------------------------------------
# Documented divergence: a large Tc inside a SINGLE Tj string. Java treats
# each Tc-widened intra-string glyph gap as a per-glyph word break and
# extracts "A B  C D"; the lite stripper holds the whole string in one
# TextPosition, never re-examines intra-run glyph gaps, and extracts
# "AB CD". This is the documented per-glyph-granularity carve-out (see the
# module docstring and CHANGES.md), not a Tc sign/scale bug — the Tc value
# is read correctly; the lite port simply does not subdivide a run. xfail
# strict so a future per-glyph emitter that closes the gap flips this green.
# ---------------------------------------------------------------------------


@requires_oracle
@pytest.mark.xfail(
    reason="Wave 1488 threaded real per-glyph advances through the lite "
    "stripper and now *subdivides* a run on intra-run Tc-widened gaps, so a "
    "large Tc inside a single Tj string segments into words: pypdfbox extracts "
    "'A B C D' (was 'AB CD'). The sole residual is the double space Java emits "
    "around the literal space glyph ('A B  C D'): Java inserts a gap-driven "
    "separator *and* keeps the explicit space glyph, whereas the lite "
    "stripper's word-break heuristic suppresses a gap separator adjacent to an "
    "already-present whitespace glyph (to avoid double-spacing when a producer "
    "encoded the break). Reconciling the double-space-adjacent-to-explicit-"
    "space rule is a whitespace-collapse change spanning the whole getText "
    "suite; the per-glyph intra-run break itself is now correct. Same family "
    "as the per-run-granularity carve-outs.",
    strict=True,
)
def test_large_char_spacing_intra_run_word_breaks_match_pdfbox() -> None:
    java_text, _jg, py_text, _pr, _ph = _roundtrip(_TC)
    assert py_text == java_text
