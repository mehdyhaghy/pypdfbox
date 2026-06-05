"""Live Apache PDFBox differential parity for horizontal text scaling
(``Tz``) and its effect on word-break detection in
``PDFTextStripper.getText()``.

PDF 32000-1 §9.3.4: the ``Tz`` operand is a *percentage* that scales the
horizontal component of every glyph displacement — and of character spacing
(``Tc``) and word spacing (``Tw``) — by ``Tz/100``. ``Tz 50`` condenses the
text to half-width; ``Tz 200`` expands it to double-width.

The headline question this surface answers is **word segmentation**: the
stripper inserts a word separator when the inter-run X gap exceeds a
font-size-relative threshold. A ``TJ``-array numeric jump that crosses the
threshold at ``Tz 100`` is *halved* under ``Tz 50`` (so it may no longer
cross it) and *doubled* under ``Tz 200`` (so a sub-threshold jump may now
cross it). So the same content stream extracts a different string depending
on ``Tz`` — and pypdfbox must match Java's segmentation in every case.

This is distinct from ``test_text_spacing_oracle.py``, which exercises a
single ``Tz 50`` ``(AB CD) Tj`` run and asserts only string parity + first-
run-origin X (where the lone explicit space governs the break, so the result
is ``Tz``-insensitive). Here the break is governed by a ``TJ`` *gap* that
``Tz`` scales, so the extracted string itself is ``Tz``-dependent.

The :class:`TextHorizScalingProbe` Java probe subclasses ``PDFTextStripper``,
emits the full extracted string (so word breaks are recovered exactly) plus
one canonical ``unicode \t xDirAdj \t yDirAdj \t widthDirAdj`` line per glyph.

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

_PROBE = "TextHorizScalingProbe"
_COORD_EPS = 0.5


# ---------------------------------------------------------------------------
# Content-stream fixtures. A ``TJ`` array with a fixed numeric jump between
# two strings, shown under different ``Tz`` percentages. The jump is chosen
# so that at ``Tz 100`` it crosses the word-break threshold; at ``Tz 50`` it
# is halved (and may drop below); at ``Tz 200`` a smaller jump is doubled
# (and may rise above).
# ---------------------------------------------------------------------------

# A very large forward jump (-2000 = 48pt at Tz 100 / Tz 200) — a gap so wide
# it crosses BOTH Java's space-relative threshold and the lite stripper's
# coarser ``font_size × 1.5`` threshold, so the two engines segment alike.
_TJ_BIG_TZ_100 = b"BT /F1 24 Tf 100 Tz 20 150 Td [(AB) -2000 (CD)] TJ ET"
_TJ_BIG_TZ_200 = b"BT /F1 24 Tf 200 Tz 20 150 Td [(AB) -2000 (CD)] TJ ET"

# Two separate Tj runs separated only by the Tz-scaled glyph advance of the
# first run — no explicit space, no TJ jump. Tz 50 condenses the AB advance,
# Tz 200 expands it; whether CD abuts or detaches is Tz-governed. Both engines
# agree there is no break (the runs abut).
_TWORUN_TZ_50 = b"BT /F1 24 Tf 50 Tz 20 150 Td (AB) Tj (CD) Tj ET"
_TWORUN_TZ_200 = b"BT /F1 24 Tf 200 Tz 20 150 Td (AB) Tj (CD) Tj ET"

# Explicit single space inside one Tj run under condensed/expanded scaling —
# the lone space governs the break regardless of Tz (control case).
_SPACE_TZ_50 = b"BT /F1 24 Tf 50 Tz 20 150 Td (AB CD) Tj ET"
_SPACE_TZ_200 = b"BT /F1 24 Tf 200 Tz 20 150 Td (AB CD) Tj ET"

# A mid-size forward jump (-700 = 16.8pt at Tz 100) under three scalings. Java
# breaks in all three (the gap-to-space-width ratio is Tz-invariant ≈ 2.5,
# above its space-relative threshold); the lite stripper's coarser
# ``font_size × 1.5`` gap threshold does not fire for a 8–34pt gap, so it does
# not break. This is the deferred word-break-threshold-calibration divergence,
# pinned below (xfail) — NOT a Tz geometry bug (the gap *is* Tz-scaled now).
_TJ_MID_TZ_100 = b"BT /F1 24 Tf 100 Tz 20 150 Td [(AB) -700 (CD)] TJ ET"
_TJ_MID_TZ_50 = b"BT /F1 24 Tf 50 Tz 20 150 Td [(AB) -700 (CD)] TJ ET"
_TJ_MID_TZ_200 = b"BT /F1 24 Tf 200 Tz 20 150 Td [(AB) -700 (CD)] TJ ET"


def _build_pdf(content: bytes, path: str) -> None:
    """Build a one-page PDF whose page content is exactly ``content``.

    The ``/F1`` token is rewritten to whatever key the page resources
    allocate for the embedded Helvetica font.
    """
    doc = PDDocument()
    try:
        page = PDPage(PDRectangle(0, 0, 400, 200))
        doc.add_page(page)
        font = PDFontFactory.create_default_font(
            Standard14Fonts.FontName.HELVETICA.value
        )
        resources = page.get_or_create_resources()
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
    __slots__ = ("unicode", "x", "y", "width")

    def __init__(self, fields: list[str]) -> None:
        self.unicode = fields[0]
        self.x = float(fields[1])
        self.y = float(fields[2])
        self.width = float(fields[3])


def _java(path: str) -> tuple[str, list[_Glyph]]:
    out = run_probe_text(_PROBE, path)
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


def _py(path: str) -> str:
    doc = PDDocument.load(path)
    try:
        stripper = PDFTextStripper()
        stripper.set_sort_by_position(True)
        return stripper.get_text(doc)
    finally:
        doc.close()


def _roundtrip(content: bytes) -> tuple[str, list[_Glyph], str]:
    with tempfile.TemporaryDirectory() as td:
        path = str(Path(td) / "case.pdf")
        _build_pdf(content, path)
        java_text, java_glyphs = _java(path)
        py_text = _py(path)
    return java_text, java_glyphs, py_text


# ---------------------------------------------------------------------------
# Headline: extracted-string parity across the Tz × gap combinations where
# the break decision lands the same in both engines — a wide TJ jump (above
# both thresholds), abutting two-run cases (no break), and the explicit-space
# control (the space glyph governs the break, Tz-independently). pypdfbox must
# reproduce Java's segmentation in every case.
# ---------------------------------------------------------------------------


@requires_oracle
@pytest.mark.parametrize(
    "content",
    [
        _TJ_BIG_TZ_100,
        _TJ_BIG_TZ_200,
        _TWORUN_TZ_50,
        _TWORUN_TZ_200,
        _SPACE_TZ_50,
        _SPACE_TZ_200,
    ],
    ids=[
        "tj_big_tz100",
        "tj_big_tz200",
        "tworun_tz50",
        "tworun_tz200",
        "space_tz50",
        "space_tz200",
    ],
)
def test_extracted_string_matches_pdfbox(content: bytes) -> None:
    java_text, _java_glyphs, py_text = _roundtrip(content)
    assert py_text == java_text


# ---------------------------------------------------------------------------
# Explicit-space control: a lone space inside one Tj run yields "AB CD"
# regardless of Tz (the break is the space glyph, not a Tz-scaled gap).
# ---------------------------------------------------------------------------


@requires_oracle
@pytest.mark.parametrize(
    "content", [_SPACE_TZ_50, _SPACE_TZ_200], ids=["tz50", "tz200"]
)
def test_explicit_space_break_is_tz_independent(content: bytes) -> None:
    java_text, _java_glyphs, py_text = _roundtrip(content)
    assert py_text == java_text == "AB CD\n"


# ---------------------------------------------------------------------------
# Tz geometry parity (the fix): the horizontal advance — hence the inter-run
# gap and the run width pypdfbox measures — is scaled by Tz/100. We prove it
# from the lite stripper's own per-run TextPositions: the AB→CD origin gap and
# the run width must scale with Tz/100 relative to the Tz=100 baseline, while
# the run origin (anchored by Td) is Tz-independent. This is the assertion the
# §9.3.4 advance-scaling fix makes true; before it, the positions were
# byte-identical for Tz 50 / 100 / 200.
# ---------------------------------------------------------------------------


def _py_runs(content: bytes) -> list[TextPosition]:
    captured: list[TextPosition] = []

    class _Capture(PDFTextStripper):
        def write_string(self, text, text_positions, sink=None):  # type: ignore[override]
            captured.extend(text_positions)
            return super().write_string(text, text_positions, sink)

    with tempfile.TemporaryDirectory() as td:
        path = str(Path(td) / "case.pdf")
        _build_pdf(content, path)
        doc = PDDocument.load(path)
        try:
            stripper = _Capture()
            stripper.set_sort_by_position(True)
            stripper.get_text(doc)
        finally:
            doc.close()
    return captured


@requires_oracle
def test_tz_scales_run_width_and_gap() -> None:
    r100 = _py_runs(_TJ_MID_TZ_100)
    r50 = _py_runs(_TJ_MID_TZ_50)
    r200 = _py_runs(_TJ_MID_TZ_200)
    assert len(r100) == len(r50) == len(r200) == 2

    def gap(runs: list[TextPosition]) -> float:
        return runs[1].x - (runs[0].x + runs[0].width)

    # Origin (anchored by Td) is Tz-independent.
    assert r50[0].x == pytest.approx(r100[0].x, abs=_COORD_EPS)
    assert r200[0].x == pytest.approx(r100[0].x, abs=_COORD_EPS)
    # Run width scales with Tz/100.
    assert r50[0].width == pytest.approx(r100[0].width * 0.5, abs=_COORD_EPS)
    assert r200[0].width == pytest.approx(r100[0].width * 2.0, abs=_COORD_EPS)
    # The inter-run gap (advance + TJ jump, both Tz-scaled) tracks Tz/100.
    assert gap(r50) == pytest.approx(gap(r100) * 0.5, abs=_COORD_EPS)
    assert gap(r200) == pytest.approx(gap(r100) * 2.0, abs=_COORD_EPS)


# ---------------------------------------------------------------------------
# Word-break-threshold calibration (wave 1488 — formerly DEFERRED). For a
# *mid-size* TJ jump (gap 8–34pt across Tz 50/100/200) Java inserts a separator
# because its threshold is relative to the space-glyph width (the gap-to-space
# ratio is Tz-invariant ≈ 2.5, above it). Wave 1488 recalibrated
# ``_is_word_break`` to upstream's space-width-relative formula
# (``min(widthOfSpace × spacingTolerance, averageCharWidth ×
# averageCharTolerance)``) using the real per-glyph widths threaded through
# ``_emit``, so the break now fires across all three Tz values — matching Java.
# ---------------------------------------------------------------------------


@requires_oracle
@pytest.mark.parametrize(
    "content",
    [_TJ_MID_TZ_100, _TJ_MID_TZ_50, _TJ_MID_TZ_200],
    ids=["tz100", "tz50", "tz200"],
)
def test_mid_size_tj_jump_word_break_matches_pdfbox(content: bytes) -> None:
    java_text, _java_glyphs, py_text = _roundtrip(content)
    assert py_text == java_text == "AB CD\n"
