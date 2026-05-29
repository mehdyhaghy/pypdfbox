"""Live Apache PDFBox differential parity for rotated-text *direction*
(``TextPosition.getDir()``) and the direction-aware reading-order grouping
``PDFTextStripper`` applies when ``sortByPosition`` is on.

The fixture ``tests/fixtures/text/rotated_text_dir.pdf`` is built by
``RotatedTextDirProbe`` (``build`` mode) so it is a known-good PDFBox-produced
file. It is a single **un-rotated** LETTER page (page ``/Rotate`` is 0) that
paints four short runs, each with its *text matrix* rotated about its own
origin by a different multiple of 90 degrees (via
``Matrix.getRotateInstance``):

* ``"Zero"``       — 0   degrees
* ``"Ninety"``     — 90  degrees
* ``"OneEighty"``  — 180 degrees
* ``"TwoSeventy"`` — 270 degrees

Because the page itself is not rotated, the only rotation is in ``Tm`` — this
isolates ``TextPosition.getDir()`` (the *text* direction) from page rotation.

Two surfaces are asserted against the live oracle:

1. **getDir() per run** — Apache PDFBox reports ``getDir()`` of 0 / 90 / 180 /
   270 matching the text-matrix rotation. The probe emits one
   ``unicode \t getDir()`` line per delivered ``TextPosition``; the lite port
   emits one ``TextPosition`` per show-text run (documented run-vs-glyph
   granularity carve-out), so the per-run direction must equal the direction
   of each glyph in that run. We assert every run's :meth:`get_dir` matches
   the direction Java reports for its first glyph, and that the per-glyph
   direction stream concatenates to the per-run text in the same sorted order.

2. **Reading-order grouping** — with ``sortByPosition`` on, upstream's
   ``TextPositionComparator`` keys on ``getDir()`` first, so the four runs are
   emitted grouped by ascending direction
   (``Zero`` / ``Ninety`` / ``OneEighty`` / ``TwoSeventy``) rather than
   interleaved by raw device coordinate. We assert ``getText`` matches Java
   byte-for-byte.

Decorated ``@requires_oracle`` so it skips cleanly without Java + the jar.
Hand-written (not ported from upstream JUnit).
"""

from __future__ import annotations

from pathlib import Path

from pypdfbox.pdmodel import PDDocument
from pypdfbox.text.pdf_text_stripper import PDFTextStripper
from pypdfbox.text.text_position import TextPosition
from tests.oracle.harness import requires_oracle, run_probe_text

_FIXTURE = (
    Path(__file__).resolve().parents[2] / "fixtures" / "text" / "rotated_text_dir.pdf"
)

_PROBE = "RotatedTextDirProbe"


def _section(blob: str, tag: str) -> str:
    """Recover the ``<<<TAG ... TAG>>>`` framed section verbatim."""
    start = blob.index(f"<<<{tag}\n") + len(f"<<<{tag}\n")
    end = blob.index(f"{tag}>>>\n", start)
    return blob[start:end]


def _java_dirs(blob: str) -> list[tuple[str, float]]:
    """Parse the per-glyph ``unicode \\t getDir()`` stream."""
    out: list[tuple[str, float]] = []
    for line in _section(blob, "DIRS").splitlines():
        if not line:
            continue
        fields = line.split("\t")
        if len(fields) != 2:
            continue
        out.append((fields[0], float(fields[1])))
    return out


def _py_runs() -> list[TextPosition]:
    """Capture pypdfbox's per-run ``TextPosition`` list (sort-by-position)."""
    captured: list[TextPosition] = []

    class _Capture(PDFTextStripper):
        def write_string(self, text, text_positions, sink=None):  # type: ignore[override]
            captured.extend(text_positions)
            return super().write_string(text, text_positions, sink)

    doc = PDDocument.load(str(_FIXTURE))
    try:
        stripper = _Capture()
        stripper.set_sort_by_position(True)
        stripper.get_text(doc)
        return captured
    finally:
        doc.close()


@requires_oracle
def test_get_text_groups_by_direction_matches_pdfbox() -> None:
    """With ``sortByPosition`` on, the four differently-rotated runs are
    emitted grouped by ascending text direction — matches Java byte-for-byte."""
    blob = run_probe_text(_PROBE, "extract", str(_FIXTURE))
    java_text = _section(blob, "TEXT")

    doc = PDDocument.load(str(_FIXTURE))
    try:
        stripper = PDFTextStripper()
        stripper.set_sort_by_position(True)
        py_text = stripper.get_text(doc)
    finally:
        doc.close()

    assert py_text == java_text
    # The grouping is by ascending getDir(): 0, 90, 180, 270.
    assert py_text == "Zero\nNinety\nOneEighty\nTwoSeventy\n"


@requires_oracle
def test_per_run_dir_matches_pdfbox() -> None:
    """Each run's ``get_dir()`` equals the direction Java reports for the
    glyphs of that run (0 / 90 / 180 / 270 matching the text-matrix rotation).

    The Java per-glyph direction stream concatenates to the lite port's
    per-run text in the same sorted reading order, so we can walk the glyph
    list and line each pypdfbox run up against its first glyph's direction.
    """
    blob = run_probe_text(_PROBE, "extract", str(_FIXTURE))
    glyphs = _java_dirs(blob)
    runs = _py_runs()

    # Granularity precondition: the per-glyph unicode stream concatenates to
    # the per-run text in the same order.
    assert "".join(g[0] for g in glyphs) == "".join(r.text for r in runs)

    idx = 0
    for run in runs:
        first_uni, first_dir = glyphs[idx]
        assert run.text[0] == first_uni
        assert run.get_dir() == first_dir
        # Every glyph within this run carries the same direction upstream.
        for k in range(len(run.text)):
            assert glyphs[idx + k][1] == first_dir
        idx += len(run.text)


@requires_oracle
def test_each_direction_present_once() -> None:
    """The fixture exercises all four right-angle directions; each run maps to
    exactly one of {0, 90, 180, 270} and all four are present."""
    runs = _py_runs()
    dirs = sorted(r.get_dir() for r in runs)
    assert dirs == [0.0, 90.0, 180.0, 270.0]
