"""Live Apache PDFBox differential parity test for the ``PDFBOX-3110``
ligature-decomposition defect (wave 1435).

``PDFBOX-3110-poems-beads.pdf`` embeds a font that maps the ``ﬁ`` ligature
to the Unicode presentation-form codepoint U+FB01 (and produces ``ﬂ`` /
other Alphabetic Presentation Forms in principle). Apache PDFBox's
``PDFTextStripper`` decomposes those presentation forms to their canonical
ASCII pair (``fi`` → ``f`` + ``i``) inside ``normalizeWord`` before
emitting a line; pypdfbox's lite extractor applied the per-word
``handle_direction`` bidi reorder but skipped the NFKC presentation-form
decomposition, so the raw ligature glyph survived into the output. The
production fix routes the lite per-word flush through ``normalize_word``
(which wraps ``handle_direction``), matching upstream's
``normalizeWord`` → ``handleDirection`` chain.

The fixture additionally exercises article-thread (``/B`` bead) reading
order, which the lite extractor does not stitch — that is a separate,
documented divergence (see ``test_text_extraction_oracle.py``'s
``test_poems_beads_order_matches_pdfbox`` xfail). This test therefore
asserts on the *character content* (the glyph→Unicode mapping that the fix
targets), not the full line ordering: after NFKC normalisation the
multiset of non-whitespace characters pypdfbox extracts must equal Java's,
and no Alphabetic-Presentation-Form ligature may survive.

Decorated ``@requires_oracle`` so it skips cleanly without Java + the jar.
Hand-written (not ported from upstream JUnit).
"""

from __future__ import annotations

import collections
from pathlib import Path

from pypdfbox.pdmodel import PDDocument
from pypdfbox.text.pdf_text_stripper import PDFTextStripper
from tests.oracle.harness import requires_oracle, run_probe_text

_FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "pdfwriter"
    / "PDFBOX-3110-poems-beads.pdf"
)


def _py_text(path: Path) -> str:
    doc = PDDocument.load(str(path))
    try:
        return PDFTextStripper().get_text(doc)
    finally:
        # try/finally so a Windows file lock is always released.
        doc.close()


@requires_oracle
def test_poems_beads_no_ligature_glyph_survives() -> None:
    """No Alphabetic Presentation Form (FB00-FB06, the ``ﬁ``/``ﬂ`` family)
    leaks into pypdfbox's output — they are decomposed to ``fi``/``fl`` to
    match Java PDFBox's ``normalizeWord``."""
    py = _py_text(_FIXTURE)
    survivors = [ch for ch in py if 0xFB00 <= ord(ch) <= 0xFB06]
    assert survivors == []


@requires_oracle
def test_poems_beads_character_content_matches_pdfbox() -> None:
    """pypdfbox and Java PDFBox extract the same multiset of non-whitespace
    characters from the fixture.

    Reading order still differs (article-thread bead stitching is a
    deferred layout feature, xfail-ed separately), so we compare the
    order-insensitive character multiset rather than the full string. Before
    the wave-1435 fix this differed by exactly the four ``ﬁ`` ligatures
    (pypdfbox emitted ``ﬁ`` where Java emitted ``f`` + ``i``); after the fix
    the multisets are equal.
    """
    py = _py_text(_FIXTURE)
    java = run_probe_text("TextExtractProbe", str(_FIXTURE))

    def _bag(s: str) -> collections.Counter[str]:
        return collections.Counter(s.replace("\n", "").replace(" ", ""))

    py_bag = _bag(py)
    java_bag = _bag(java)
    assert py_bag - java_bag == collections.Counter()
    assert java_bag - py_bag == collections.Counter()


@requires_oracle
def test_poems_beads_decomposed_words_present() -> None:
    """The three French words whose ``fi`` was a U+FB01 ligature in the
    content stream — ``fit`` / ``afin`` / ``clarifié`` — appear with the
    decomposed ASCII pair, exactly as Java extracts them."""
    py = _py_text(_FIXTURE)
    for word in ("fit", "afin", "clarifié"):
        assert word in py
