"""Live Apache PDFBox differential parity for separator-token placement.

The default ``PDFTextStripper`` separators (word=``" "``, line=``"\\n"``,
pageEnd=``"\\n"``, page/paragraph start=``""``) all render as plain
whitespace, so a separator inserted in the wrong place is invisible in a
default-config diff: a stray space looks like an intended one. This probe
overrides every separator with a unique sentinel token so the *exact*
insertion point of each word break, line break, page break, and paragraph
break becomes observable, then asserts pypdfbox's :class:`PDFTextStripper`
places them identically to Java PDFBox 3.0.7.

``with_outline.pdf`` is a 6-page document that already matches Java
byte-for-byte under the default config (see
``test_text_extraction_oracle.py``); running it through the
sentinel-separator config additionally pins the *placement* of every
word / line / page break — i.e. that those hooks fire at the same
boundaries in both engines, not merely that whitespace happens to coincide.

The one separator whose placement diverges is the *paragraph* delimiter
(``setParagraphStart`` / ``setParagraphEnd``): upstream wraps every
visual line of this fixture in a paragraph because its
``isParagraphSeparation`` indent test fires on the stair-stepped left
margin of the bookmark headings ("First level 1" / "First level 2" / …
each indented further). That indent / hanging-indent / list-item
paragraph-detection heuristic is a deferred layout feature of the lite
stripper (see ``PDFTextStripper`` docstring and the eu-001 / poems-beads
xfails); it is pinned as ``xfail`` here with a precise reason rather than
weakened. Word / line / page placement — everything *except* the
paragraph tokens — is at full parity and asserted positively below.

``@requires_oracle`` so it skips cleanly without Java + the jar.
Hand-written (not ported from upstream JUnit).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.pdmodel import PDDocument
from pypdfbox.text.pdf_text_stripper import PDFTextStripper
from tests.oracle.harness import requires_oracle, run_probe_text

_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"
_FIXTURE = _FIXTURES / "pdmodel" / "with_outline.pdf"


def _py_text_with_sentinels(path: Path) -> str:
    doc = PDDocument.load(str(path))
    try:
        stripper = PDFTextStripper()
        stripper.set_sort_by_position(True)
        stripper.set_word_separator("|W|")
        stripper.set_line_separator("|L|\n")
        stripper.set_page_start("<<PAGE>>")
        stripper.set_page_end("<</PAGE>>\n")
        stripper.set_paragraph_start("[P]")
        stripper.set_paragraph_end("[/P]")
        return stripper.get_text(doc)
    finally:
        doc.close()


def _strip_paragraph_tokens(text: str) -> str:
    """Remove the paragraph sentinels, leaving word/line/page placement."""
    return text.replace("[P]", "").replace("[/P]", "")


@requires_oracle
def test_word_line_page_separator_placement_matches_pdfbox() -> None:
    """Every word / line / page separator lands at the same boundary as
    Java PDFBox when overridden to a distinctive sentinel token (paragraph
    tokens excluded — see module docstring + the paragraph xfail below)."""
    java = run_probe_text("TextSeparatorProbe", str(_FIXTURE))
    py = _py_text_with_sentinels(_FIXTURE)
    assert _strip_paragraph_tokens(py) == _strip_paragraph_tokens(java)


@requires_oracle
def test_page_sentinels_fire_once_per_page() -> None:
    """The page-start / page-end sentinels fire exactly once per extracted
    page in both engines (6-page fixture)."""
    java = run_probe_text("TextSeparatorProbe", str(_FIXTURE))
    py = _py_text_with_sentinels(_FIXTURE)
    assert py.count("<<PAGE>>") == java.count("<<PAGE>>")
    assert py.count("<</PAGE>>") == java.count("<</PAGE>>")
    assert py.count("<<PAGE>>") == 6


@requires_oracle
@pytest.mark.xfail(
    reason="Paragraph-token placement: upstream's isParagraphSeparation wraps "
    "every visual line of with_outline.pdf in a [P]…[/P] pair because its "
    "indent test fires on the stair-stepped left margin of the bookmark "
    "headings (each 'level N' heading is indented further than the last), and "
    "it emits a leading paragraphStart at page start / trailing paragraphEnd "
    "at page end. The lite stripper's paragraph heuristic only emits the "
    "delimiters at a detected vertical-drop break and does not run upstream's "
    "indent / hanging-indent / list-item paragraph detection — a deferred "
    "layout feature (PDFTextStripper docstring), same family as the eu-001 "
    "multi-column and poems-beads xfails. Word/line/page placement is at full "
    "parity (asserted above).",
    strict=True,
)
def test_paragraph_token_placement_matches_pdfbox() -> None:
    java = run_probe_text("TextSeparatorProbe", str(_FIXTURE))
    py = _py_text_with_sentinels(_FIXTURE)
    assert py == java
