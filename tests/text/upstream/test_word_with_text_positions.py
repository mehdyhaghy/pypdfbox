"""
No dedicated upstream test class exists for ``WordWithTextPositions`` in
Apache PDFBox 3.0:

  - Upstream defines it as a ``private static final`` inner class of
    ``org.apache.pdfbox.text.PDFTextStripper`` (lines ~2171-2191), so it
    is not directly testable from outside the stripper.

The pypdfbox port promotes it to a public top-level type to make the
data-holder reusable by downstream pipelines. The assertions below
mirror the upstream contract:

  - constructor stores the (text, positions) pair verbatim;
  - ``get_text()`` returns the text;
  - ``get_text_positions()`` returns the positions list as-is (not a
    defensive copy);
  - the number of entries in the positions list may differ from the
    number of characters in the text due to normalization.
"""

from __future__ import annotations

from pypdfbox.text import TextPosition, WordWithTextPositions


def _tp(text: str) -> TextPosition:
    return TextPosition(text=text, x=0.0, y=0.0, font_size=12.0)


def test_get_text() -> None:
    word = WordWithTextPositions("hello", [_tp("h"), _tp("i")])
    assert word.get_text() == "hello"


def test_get_text_positions() -> None:
    positions = [_tp("h"), _tp("i")]
    word = WordWithTextPositions("hi", positions)
    assert word.get_text_positions() is positions


def test_text_and_positions_lengths_may_differ() -> None:
    # Upstream Javadoc explicitly notes: "the number of entries in that
    # list may differ from the number of characters in the string due
    # to normalization."
    word = WordWithTextPositions("a", [_tp("a"), _tp("́")])
    assert len(word.get_text()) != len(word.get_text_positions())
