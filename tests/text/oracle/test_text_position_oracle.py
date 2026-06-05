"""Live Apache PDFBox differential parity tests for per-glyph ``TextPosition``
geometry.

The ``TextPosGeomProbe`` subclasses ``PDFTextStripper`` and overrides
``writeString(String, List<TextPosition>)`` to emit one canonical,
tab-separated line per glyph::

    unicode \t getXDirAdj() \t getYDirAdj() \t getWidthDirAdj() \t
    getHeightDir() \t getFontSizeInPt()

(all floats ``%.2f`` with ``Locale.ROOT`` so the rendering is stable
across platforms). pypdfbox is a *lite* port: its stripper emits one
:class:`~pypdfbox.text.TextPosition` per *show-text run* (a ``Tj`` / ``TJ``
chunk), not one per glyph. So the comparison reconciles the two
granularities — the Java per-glyph unicode stream concatenates exactly to
pypdfbox's per-run text in the same sorted reading order (asserted), which
lets us walk the Java glyph list and line each pypdfbox run up against its
first glyph's geometry.

Reference frame reconciliation (all pre-existing, documented lite-port
carve-outs — see ``CHANGES.md`` ``TextPosition`` lite-port note and the
``PDFTextStripper`` docstring; none is a regression introduced or fixable
here without overturning a documented design decision):

* **Y axis** — Apache PDFBox's ``getYDirAdj()`` is measured from the page
  *top* (y-down, upper-left origin); pypdfbox keeps the PDF user-space
  y-up (lower-left origin) value on the position and the internal
  reading-order sort relies on that. The two relate by
  ``java_y == page_height - py.y`` for an unrotated page. The test applies
  that flip rather than weakening the assertion.
* **Per-glyph granularity / X drift** — pypdfbox advances the text cursor
  by the font's *average* glyph advance, not the true per-glyph width, so
  a run's *origin* matches Java (the cursor is re-anchored by ``Tm`` /
  ``Td`` at every line break) but x accumulates drift along a line when
  the font's glyph widths are non-uniform. We therefore assert tight
  parity on (a) every run origin for a uniform-advance fixture and (b) the
  *first run of each line* (line origins) for a proportional-font fixture,
  and document the intra-line drift.
* **Height** — ``getHeightDir()`` is the glyph's font-bounding-box height
  (e.g. 8.19pt at a 12pt size); the lite port returns the font size as the
  height proxy. Not asserted (deferred per-glyph metric).
* **getFontSizeInPt rounding** — Java's ``getFontSizeInPt()`` re-derives
  the rendered size through the CTM and rounds to an integer point size
  (18.0 where ``getFontSize()`` is 18.2); pypdfbox reports the effective
  ``Tf``×scale size. The residual is sub-0.5pt, inside ``_FS_EPS``.

EPSILON: ``_COORD_EPS = 0.5`` (pt) for coordinates and ``_FS_EPS = 0.5``
(pt) for font size — comfortably sub-half-point, the granularity at which
the 2-decimal probe rounding and the float text-matrix algebra agree.

Decorated ``@requires_oracle`` so it skips cleanly without Java + the jar.
Hand-written (not ported from upstream JUnit).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.pdmodel import PDDocument
from pypdfbox.text.pdf_text_stripper import PDFTextStripper
from pypdfbox.text.text_position import TextPosition
from tests.oracle.harness import requires_oracle, run_probe_text

_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"

_PROBE = "TextPosGeomProbe"
_COORD_EPS = 0.5
_FS_EPS = 0.5


class _Glyph:
    """One parsed line of the Java probe's per-glyph output."""

    __slots__ = ("unicode", "x_dir_adj", "y_dir_adj", "width_dir_adj", "height_dir", "fs_pt")

    def __init__(self, fields: list[str]) -> None:
        self.unicode = fields[0]
        self.x_dir_adj = float(fields[1])
        self.y_dir_adj = float(fields[2])
        self.width_dir_adj = float(fields[3])
        self.height_dir = float(fields[4])
        self.fs_pt = float(fields[5])


def _java_glyphs(rel: str, page: int = 1) -> list[_Glyph]:
    """Run the Java oracle probe and parse its per-glyph geometry lines."""
    out = run_probe_text(_PROBE, str(_FIXTURES / rel), str(page))
    glyphs: list[_Glyph] = []
    for line in out.splitlines():
        if not line:
            continue
        # The unicode column may itself be a tab-free single character; the
        # probe joins exactly six columns with a literal tab.
        fields = line.split("\t")
        if len(fields) != 6:
            continue
        glyphs.append(_Glyph(fields))
    return glyphs


def _py_runs(rel: str, page: int = 1) -> tuple[list[TextPosition], float, float]:
    """Capture pypdfbox's per-run ``TextPosition`` list for one page.

    Returns ``(positions, page_width, page_height)`` with the document
    closed in a ``finally`` so a Windows file lock is always released.
    The positions are captured in the exact order the stripper hands them
    to ``write_string`` (sort-by-position is enabled to mirror the probe).
    """
    captured: list[TextPosition] = []

    class _Capture(PDFTextStripper):
        def write_string(self, text, text_positions, sink=None):  # type: ignore[override]
            captured.extend(text_positions)
            return super().write_string(text, text_positions, sink)

    doc = PDDocument.load(str(_FIXTURES / rel))
    try:
        page_obj = doc.get_page(page - 1)
        media = page_obj.get_media_box()
        pw, ph = media.get_width(), media.get_height()
        stripper = _Capture()
        stripper.set_sort_by_position(True)
        stripper.set_start_page(page)
        stripper.set_end_page(page)
        stripper.get_text(doc)
        return captured, pw, ph
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# Granularity reconciliation — the per-glyph stream must concatenate to the
# per-run text. This is the precondition for lining runs up against glyphs.
# ---------------------------------------------------------------------------


@requires_oracle
@pytest.mark.parametrize("rel", ["pdfwriter/unencrypted.pdf", "pdmodel/with_outline.pdf"])
def test_glyph_stream_concatenates_to_run_text(rel: str) -> None:
    glyphs = _java_glyphs(rel)
    runs, _pw, _ph = _py_runs(rel)
    java_unicode = "".join(g.unicode for g in glyphs)
    py_unicode = "".join(r.text for r in runs)
    assert py_unicode == java_unicode


# ---------------------------------------------------------------------------
# Uniform-advance fixture: every run origin matches Java to <0.5pt on x, on
# the flipped y, and on the effective font size.
# ---------------------------------------------------------------------------


@requires_oracle
def test_unencrypted_per_run_geometry_matches_pdfbox() -> None:
    """``unencrypted.pdf`` uses a single Helvetica-class font whose
    ``/Widths`` give an average advance close to the true per-glyph
    widths, so the cursor stays aligned across each whole line. Every
    run's origin (x, flipped y) and font size match Java within epsilon.
    """
    glyphs = _java_glyphs("pdfwriter/unencrypted.pdf")
    runs, _pw, ph = _py_runs("pdfwriter/unencrypted.pdf")
    assert "".join(r.text for r in runs) == "".join(g.unicode for g in glyphs)

    idx = 0
    for run in runs:
        first = glyphs[idx]
        assert run.text[0] == first.unicode
        assert run.x == pytest.approx(first.x_dir_adj, abs=_COORD_EPS)
        # Flip pypdfbox's y-up (lower-left) value into Java's y-down frame.
        assert (ph - run.y) == pytest.approx(first.y_dir_adj, abs=_COORD_EPS)
        assert run.get_font_size_in_pt() == pytest.approx(first.fs_pt, abs=_FS_EPS)
        idx += len(run.text)


# ---------------------------------------------------------------------------
# Proportional-font fixture: line origins match; intra-line x drift is the
# documented average-advance approximation (deferred per-glyph widths).
# ---------------------------------------------------------------------------


@requires_oracle
def test_with_outline_line_origins_match_pdfbox() -> None:
    """``with_outline.pdf`` uses a proportional TrueType font. The lite
    stripper advances by the font's *average* glyph width, so x drifts
    within a line; but the first run after every line break is re-anchored
    by ``Tm`` / ``Td`` and so its origin matches Java. We assert the line
    origins (x + flipped y + font size) and document the intra-line drift.
    """
    glyphs = _java_glyphs("pdmodel/with_outline.pdf")
    runs, _pw, ph = _py_runs("pdmodel/with_outline.pdf")
    assert "".join(r.text for r in runs) == "".join(g.unicode for g in glyphs)

    idx = 0
    prev_y: float | None = None
    checked_line_origins = 0
    for run in runs:
        first = glyphs[idx]
        is_new_line = prev_y is None or abs(run.y - prev_y) > 0.5 * run.font_size
        if is_new_line:
            # Line origin: x re-anchored by Tm/Td matches Java within a
            # glyph width; flipped y and font size match within epsilon.
            assert run.x == pytest.approx(first.x_dir_adj, abs=2.0)
            assert (ph - run.y) == pytest.approx(first.y_dir_adj, abs=_COORD_EPS)
            assert run.get_font_size_in_pt() == pytest.approx(first.fs_pt, abs=_FS_EPS)
            checked_line_origins += 1
        # The flipped y must always match regardless of intra-line x drift.
        assert (ph - run.y) == pytest.approx(first.y_dir_adj, abs=_COORD_EPS)
        prev_y = run.y
        idx += len(run.text)

    assert checked_line_origins >= 3


@requires_oracle
def test_with_outline_intra_line_x_origin_matches_pdfbox() -> None:
    """Intra-line X parity (wave 1488): each run's origin X now matches the
    Java glyph at the run's start index, within coordinate epsilon.

    Formerly ``test_with_outline_intra_line_x_drift_is_horizontal_only`` —
    that test *documented* the intra-line X drift caused by the lite
    stripper's font-wide average glyph advance. Wave 1488 threaded real
    per-glyph advances (the font's ``/Widths``, decoded code-by-code) through
    ``_emit``, so the X cursor now steps exactly the way
    ``PDFStreamEngine.showText`` does and the drift is gone (it was ~0.005pt
    across the whole fixture, down from many points). Each run's origin X
    therefore lands on the Java glyph at its first-character index, and the
    flipped Y / font size stay exact as before.
    """
    glyphs = _java_glyphs("pdmodel/with_outline.pdf")
    runs, _pw, ph = _py_runs("pdmodel/with_outline.pdf")

    idx = 0
    max_dx_seen = 0.0
    for run in runs:
        first = glyphs[idx]
        dx = abs(run.x - first.x_dir_adj)
        # X origin now tracks the real per-glyph advance — at parity with
        # the Java glyph at this run's start.
        assert run.x == pytest.approx(first.x_dir_adj, abs=_COORD_EPS)
        # Flipped Y stays exact (the frame/rotation was never the issue).
        assert (ph - run.y) == pytest.approx(first.y_dir_adj, abs=_COORD_EPS)
        max_dx_seen = max(max_dx_seen, dx)
        idx += len(run.text)

    # Drift is now within coordinate epsilon across the whole fixture.
    assert max_dx_seen <= _COORD_EPS, (
        "real per-glyph advances should eliminate the intra-line X drift"
    )


# ---------------------------------------------------------------------------
# Rotated fixture: pypdfbox does not fold the page /Rotate into the CTM
# (the producer bakes the rotation into the text matrix instead), so it
# never sets dir/page geometry on the position. The run still carries the
# correct device origin in its own un-rotated y-up frame — it relates to
# Java's direction-adjusted coords by an axis swap. Documented, asserted.
# ---------------------------------------------------------------------------


@requires_oracle
def test_rot90_run_origin_reconciles_with_pdfbox() -> None:
    """``rot90.pdf`` is a 90-degree page. Apache PDFBox's ``getDir()`` is
    90 and ``getXDirAdj`` / ``getYDirAdj`` undo the rotation. pypdfbox's
    lite stripper leaves the page rotation in the text matrix and reports
    the device origin in its own y-up frame, so the mapping is an axis
    swap: ``java_x_dir_adj == py.y`` and ``java_y_dir_adj == py.x``. Font
    size is rotation-invariant and matches directly. (Documented in
    ``CHANGES.md`` — page-/Rotate-not-in-CTM lite carve-out.)
    """
    glyphs = _java_glyphs("multipdf/rot90.pdf")
    runs, _pw, _ph = _py_runs("multipdf/rot90.pdf")
    assert "".join(r.text for r in runs) == "".join(g.unicode for g in glyphs)

    first_run = runs[0]
    first_glyph = glyphs[0]
    assert first_run.y == pytest.approx(first_glyph.x_dir_adj, abs=_COORD_EPS)
    assert first_run.x == pytest.approx(first_glyph.y_dir_adj, abs=_COORD_EPS)
    assert first_run.get_font_size_in_pt() == pytest.approx(first_glyph.fs_pt, abs=_FS_EPS)
