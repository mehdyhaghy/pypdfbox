"""Live Apache PDFBox differential parity for text rise (``Ts``) extraction.

``Ts`` (PDF 32000-1 §9.3.7) raises or lowers the baseline of subsequent
glyphs by shifting the text-rendering matrix origin vertically by the rise
— the mechanism behind superscripts and subscripts. Two facets matter to
``PDFTextStripper``:

1. **Inline extraction.** A superscript / subscript run sits only slightly
   off the main baseline (the rise is well within the stripper's line
   tolerance), so it must extract *inline* with the surrounding text — no
   spurious line break is inserted around the raised run. The default line
   separator (``"\n"``) collapses onto whitespace and would hide a stray
   newline, so this module overrides the line separator with the
   distinctive sentinel ``"|L|"`` (matching the Java probe) to make any
   spurious break directly observable.
2. **Per-run baseline Y.** The raised run's glyph origins reflect the rise:
   a ``+8 Ts`` run sits 8 pt *above* the baseline, a ``-6 Ts`` run 6 pt
   *below* it. Apache PDFBox folds the rise into the text-rendering matrix
   (``parameterMatrix × textMatrix × ctm`` with the rise in the parameter
   matrix's f-translation), so its ``getYDirAdj()`` shifts by exactly the
   rise. pypdfbox now folds the rise the same way (lite-port: font size is
   applied separately, so the rise-bearing parameter matrix is the bare
   translation ``[1, 0, 0, 1, 0, rise]``).

The :class:`TextRiseProbe` Java probe subclasses ``PDFTextStripper``, emits
the framed extracted string and one ``unicode \t yDirAdj`` line per glyph in
reading order. pypdfbox is a lite per-*run* stripper (one ``TextPosition``
per show-text run, not per glyph), so the comparison reconciles the two
granularities: the per-glyph yDirAdj is constant across a run (every glyph
of a run shares the run's baseline), so each pypdfbox run's flipped y
(``page_height − run.y``) is compared against the yDirAdj of the Java glyphs
that make up that run.

Reference-frame reconciliation (pre-existing lite-port carve-out): Apache
PDFBox's ``getYDirAdj()`` is measured from the page *top* (y-down);
pypdfbox keeps the PDF user-space y-up value on the position. They relate by
``java_y == page_height − py.y`` on an unrotated page — the test applies
that flip rather than weakening the assertion.

EPSILON: ``_COORD_EPS = 0.5`` pt — comfortably sub-half-point, the
granularity at which the 2-decimal probe rounding and the float text-matrix
algebra agree.

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

_PROBE = "TextRiseProbe"
_COORD_EPS = 0.5
_PAGE_W = 400.0
_PAGE_H = 200.0

# A baseline run, a superscript run (+8 Ts), then the rise reset (0 Ts) for a
# third baseline run — all on the same Td baseline, one BT block. The rise is
# small enough to stay within the stripper's line tolerance, so the whole
# thing extracts inline as one logical line.
_SUPER = b"BT /F1 24 Tf 20 150 Td (base ) Tj 8 Ts (super ) Tj 0 Ts (more) Tj ET"
# A subscript run (-6 Ts) lowered below the baseline, then reset.
_SUB = b"BT /F1 24 Tf 20 150 Td (base ) Tj -6 Ts (sub ) Tj 0 Ts (more) Tj ET"
# Rise set but never reset: the final run stays raised (the state persists
# until an explicit 0 Ts), matching upstream text-state semantics.
_PERSIST = b"BT /F1 24 Tf 20 150 Td (low ) Tj 5 Ts (highrest) Tj ET"


def _build_pdf(content: bytes, path: str) -> None:
    """Build a one-page PDF whose page content is exactly ``content``.

    The ``/F1`` token is rewritten to whatever key the page resources
    actually allocate for the embedded Helvetica font.
    """
    doc = PDDocument()
    try:
        page = PDPage(PDRectangle(0, 0, _PAGE_W, _PAGE_H))
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
    """One parsed glyph line from the probe's GLYPHS section: unicode, y."""

    __slots__ = ("unicode", "y")

    def __init__(self, fields: list[str]) -> None:
        self.unicode = fields[0]
        self.y = float(fields[1])


def _java(path: str) -> tuple[str, list[_Glyph]]:
    """Run the probe; return ``(extracted_text, glyphs)``.

    The probe frames the extracted text as ``<<<TEXT\n{text}TEXT>>>\n`` —
    split on the bare sentinels so the extracted text (including its own
    trailing newline / page separator) is preserved byte-for-byte.
    """
    out = run_probe_text(_PROBE, path)
    text_part = out.split("<<<TEXT\n", 1)[1].split("TEXT>>>\n", 1)[0]
    glyph_part = out.split("<<<GLYPHS\n", 1)[1].split("GLYPHS>>>", 1)[0]
    glyphs: list[_Glyph] = []
    for line in glyph_part.splitlines():
        if not line:
            continue
        fields = line.split("\t")
        if len(fields) != 2:
            continue
        glyphs.append(_Glyph(fields))
    return text_part, glyphs


def _py(path: str) -> tuple[str, list[TextPosition]]:
    """Extract with pypdfbox; return ``(text, runs)``.

    The line separator is the distinctive ``"|L|"`` sentinel (matching the
    probe) so a spurious newline around a raised run is observable. The
    document is closed in a ``finally`` so a Windows file lock is always
    released.
    """
    captured: list[TextPosition] = []

    class _Capture(PDFTextStripper):
        def write_string(self, text, text_positions, sink=None):  # type: ignore[override]
            captured.extend(text_positions)
            return super().write_string(text, text_positions, sink)

    doc = PDDocument.load(path)
    try:
        stripper = _Capture()
        stripper.set_sort_by_position(True)
        stripper.set_line_separator("|L|")
        text = stripper.get_text(doc)
        return text, captured
    finally:
        doc.close()


def _roundtrip(content: bytes) -> tuple[str, list[_Glyph], str, list[TextPosition]]:
    """Build the PDF, run both Java and pypdfbox over it."""
    with tempfile.TemporaryDirectory() as td:
        path = str(Path(td) / "case.pdf")
        _build_pdf(content, path)
        java_text, java_glyphs = _java(path)
        py_text, py_runs = _py(path)
    return java_text, java_glyphs, py_text, py_runs


# ---------------------------------------------------------------------------
# Inline extraction — the headline metric. A super/subscript run stays on the
# same logical line as the surrounding text: no spurious line break, exact
# string parity with Java (the "|L|" sentinel makes any stray break visible).
# ---------------------------------------------------------------------------


@requires_oracle
@pytest.mark.parametrize(
    "content", [_SUPER, _SUB, _PERSIST], ids=["super", "sub", "persist"]
)
def test_rise_run_extracts_inline_matching_pdfbox(content: bytes) -> None:
    java_text, _jg, py_text, _pr = _roundtrip(content)
    # Exact string parity, including the absence of any "|L|" line break
    # around the raised/lowered run.
    assert py_text == java_text
    assert "|L|" not in py_text
    assert "|L|" not in java_text


# ---------------------------------------------------------------------------
# Per-run baseline Y — the rise shifts the raised run's origin by exactly the
# Ts value, matching Java's per-glyph yDirAdj after the y-up/y-down flip.
# ---------------------------------------------------------------------------


@requires_oracle
def test_superscript_run_is_raised_by_the_rise() -> None:
    """The ``+8 Ts`` run sits 8 pt above the baseline; the surrounding
    baseline runs are unshifted. pypdfbox's flipped run-Y matches Java's
    per-glyph yDirAdj for the matching run within epsilon."""
    java_text, java_glyphs, py_text, py_runs = _roundtrip(_SUPER)
    assert py_text == java_text
    by_text = {r.text: r for r in py_runs}
    assert set(by_text) == {"base ", "super ", "more"}

    # Java baseline yDirAdj (the "base" glyphs) and the raised run's yDirAdj.
    # Pick glyphs unique to each run: 'b' only in "base", 'u' only in "super".
    base_y = next(g.y for g in java_glyphs if g.unicode == "b")
    super_y = next(g.y for g in java_glyphs if g.unicode == "u")
    # Raised run sits *higher* on the page -> smaller yDirAdj (y-down origin)
    # by exactly the +8 rise.
    assert base_y - super_y == pytest.approx(8.0, abs=_COORD_EPS)

    # pypdfbox: flip each run's y-up value into Java's y-down frame.
    assert (_PAGE_H - by_text["base "].y) == pytest.approx(base_y, abs=_COORD_EPS)
    assert (_PAGE_H - by_text["super "].y) == pytest.approx(super_y, abs=_COORD_EPS)
    assert (_PAGE_H - by_text["more"].y) == pytest.approx(base_y, abs=_COORD_EPS)
    # The superscript run is 8 pt above the baseline runs in pypdfbox too.
    assert by_text["super "].y - by_text["base "].y == pytest.approx(8.0, abs=_COORD_EPS)


@requires_oracle
def test_subscript_run_is_lowered_by_the_rise() -> None:
    """The ``-6 Ts`` run sits 6 pt below the baseline; matches Java."""
    java_text, java_glyphs, py_text, py_runs = _roundtrip(_SUB)
    assert py_text == java_text
    by_text = {r.text: r for r in py_runs}
    assert set(by_text) == {"base ", "sub ", "more"}

    # 'a' only in "base", 'u' only in "sub" — disambiguate the shared 's'/'b'.
    base_y = next(g.y for g in java_glyphs if g.unicode == "a")
    sub_y = next(g.y for g in java_glyphs if g.unicode == "u")
    # Lowered run sits lower on the page -> larger yDirAdj by exactly 6 pt.
    assert sub_y - base_y == pytest.approx(6.0, abs=_COORD_EPS)

    assert (_PAGE_H - by_text["base "].y) == pytest.approx(base_y, abs=_COORD_EPS)
    assert (_PAGE_H - by_text["sub "].y) == pytest.approx(sub_y, abs=_COORD_EPS)
    # The subscript run is 6 pt below the baseline runs in pypdfbox too.
    assert by_text["base "].y - by_text["sub "].y == pytest.approx(6.0, abs=_COORD_EPS)


@requires_oracle
def test_rise_persists_until_reset() -> None:
    """An un-reset ``5 Ts`` keeps the trailing run raised — the rise is a
    text-state parameter that persists until an explicit ``0 Ts`` (matching
    upstream text-state semantics). The first run is on the baseline, the
    second is raised 5 pt, and Java agrees."""
    java_text, java_glyphs, py_text, py_runs = _roundtrip(_PERSIST)
    assert py_text == java_text
    by_text = {r.text: r for r in py_runs}
    assert set(by_text) == {"low ", "highrest"}

    base_y = next(g.y for g in java_glyphs if g.unicode == "l")
    raised_y = next(g.y for g in java_glyphs if g.unicode == "h")
    assert base_y - raised_y == pytest.approx(5.0, abs=_COORD_EPS)

    assert (_PAGE_H - by_text["low "].y) == pytest.approx(base_y, abs=_COORD_EPS)
    assert (_PAGE_H - by_text["highrest"].y) == pytest.approx(raised_y, abs=_COORD_EPS)
    assert by_text["highrest"].y - by_text["low "].y == pytest.approx(5.0, abs=_COORD_EPS)
