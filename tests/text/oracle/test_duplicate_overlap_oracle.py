"""Live Apache PDFBox differential parity for duplicate-overlapping-text
suppression (``PDFTextStripper.setSuppressDuplicateOverlappingText``).

A common fake-bold / drop-shadow technique paints the *same* word twice at
(nearly) the same position — ``Tj`` then a sub-glyph ``Td`` offset then the
same ``Tj``. With the upstream default
``setSuppressDuplicateOverlappingText(true)`` the coincident glyphs must
collapse so the extracted text shows the word ONCE, not doubled.

The fixture ``tests/fixtures/text/fake_bold_overlap.pdf`` is built by the
``DuplicateOverlapProbe`` (``build`` mode) so it is a known-good PDFBox-
produced file: "Hello" painted, then re-painted at ``(72.4, 700.2)`` (a
0.4 pt offset, far below a glyph advance), plus a genuine "World" that must
never be suppressed. The probe's ``extract`` mode emits the text with
suppression on (default) and off, framed by sentinels.

The suppression-ON surface — the actual target of this wave — matches Java
PDFBox byte-for-byte. The suppression-OFF case diverges only because of the
documented lite-port carve-out "one ``TextPosition`` per show-text run (not
per glyph)" (see ``CHANGES.md``): Java sorts the two coincident runs at
glyph granularity (``HHeelllloo``) whereas the lite stripper keeps each
show-text run contiguous (``HelloHello``). That granularity difference is
orthogonal to duplicate suppression, so the OFF case is ``xfail``-pinned
with a precise reason rather than weakened.

Decorated ``@requires_oracle`` so it skips cleanly without Java + the jar.
Hand-written (not ported from upstream JUnit).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.pdmodel import PDDocument
from pypdfbox.text.pdf_text_stripper import PDFTextStripper
from tests.oracle.harness import requires_oracle, run_probe_text

_FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "text"
    / "fake_bold_overlap.pdf"
)


def _section(blob: str, tag: str) -> str:
    """Recover the ``<<<TAG ... TAG>>>`` framed section verbatim."""
    start = blob.index(f"<<<{tag}\n") + len(f"<<<{tag}\n")
    end = blob.index(f"{tag}>>>\n", start)
    return blob[start:end]


def _py_text(suppress: bool) -> str:
    doc = PDDocument.load(str(_FIXTURE))
    try:
        stripper = PDFTextStripper()
        stripper.set_sort_by_position(True)
        stripper.set_suppress_duplicate_overlapping_text(suppress)
        return stripper.get_text(doc)
    finally:
        doc.close()


@requires_oracle
def test_suppress_on_collapses_fake_bold_matches_pdfbox() -> None:
    """Default suppression collapses the doubled word — matches Java."""
    blob = run_probe_text("DuplicateOverlapProbe", "extract", str(_FIXTURE))
    java = _section(blob, "ON")
    py = _py_text(suppress=True)
    assert py == java
    # The word appears once, not doubled, and the genuine second word stays.
    assert py == "Hello\nWorld\n"


@requires_oracle
def test_suppress_default_is_true() -> None:
    """pypdfbox's default matches upstream's default (suppression on), so the
    no-argument stripper produces the collapsed text without an explicit
    ``set_suppress_duplicate_overlapping_text`` call."""
    assert PDFTextStripper().is_suppress_duplicate_overlapping_text() is True
    doc = PDDocument.load(str(_FIXTURE))
    try:
        stripper = PDFTextStripper()
        stripper.set_sort_by_position(True)
        py = stripper.get_text(doc)
    finally:
        doc.close()
    assert py == "Hello\nWorld\n"


@requires_oracle
@pytest.mark.xfail(
    reason="Suppression-OFF diverges only on the documented lite-port carve-out "
    "'one TextPosition per show-text run, not per glyph' (CHANGES.md, wave-1409 "
    "era). With suppression off Java sorts the two coincident 'Hello' runs at "
    "glyph granularity -> 'HHeelllloo'; the lite stripper keeps each show-text "
    "run contiguous -> 'HelloHello'. This is the run-vs-glyph granularity trait, "
    "orthogonal to duplicate suppression (the ON surface matches byte-for-byte). "
    "Pinned, not weakened.",
    strict=True,
)
def test_suppress_off_keeps_both_paints_matches_pdfbox() -> None:
    blob = run_probe_text("DuplicateOverlapProbe", "extract", str(_FIXTURE))
    java = _section(blob, "OFF")
    py = _py_text(suppress=False)
    assert py == java
