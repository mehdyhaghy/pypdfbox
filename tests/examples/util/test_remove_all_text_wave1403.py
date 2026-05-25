"""Wave 1403 branch round-out for ``remove_all_text``.

Closes two empty-token-list partials in ``create_tokens_without_text``:

* ``134->136`` — a text-show operator (``Tj`` / ``TJ`` / ``'``) encountered
  with **no** preceding token leaves ``new_tokens`` empty, so the
  ``if new_tokens`` pop guard takes its False arc and the parser simply
  advances to the next token.
* ``140->139`` — a ``SHOW_TEXT_LINE_AND_SPACE`` (``"``) operator with fewer
  than three preceding tokens drives the inner ``for _ in range(3)`` loop's
  ``if new_tokens`` False arc.
"""

from __future__ import annotations

from pypdfbox.examples.util.remove_all_text import RemoveAllText
from pypdfbox.io.random_access_read_buffer import RandomAccessReadBuffer


def test_show_text_operator_with_no_preceding_token() -> None:
    """A ``Tj`` operator appearing before any operand → empty ``new_tokens``
    when the pop guard is reached (134->136)."""
    src = b"Tj BT ET"
    toks = RemoveAllText.create_tokens_without_text(RandomAccessReadBuffer(src))
    # The leading ``Tj`` was dropped; nothing was popped (none preceded it).
    reprs = [repr(t) for t in toks]
    assert not any("Tj" in r for r in reprs)


def test_quotation_operator_with_too_few_preceding_tokens() -> None:
    """A ``"`` operator with no preceding operands drives the inner
    three-pop loop's empty-list arc (140->139)."""
    src = b'" BT ET'
    toks = RemoveAllText.create_tokens_without_text(RandomAccessReadBuffer(src))
    reprs = [repr(t) for t in toks]
    assert not any('"' in r for r in reprs)
