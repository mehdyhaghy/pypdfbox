"""Wave 1370 — sort stability across LineItem / WordWithTextPositions.

Java ``Collections.sort`` is stable since the 1.4 release, and Python's
``sorted`` shares the contract. When ``set_sort_by_position(True)``
re-orders positions before formatting, ties must collapse in
insertion order. These tests pin the contract end-to-end and at the
data-holder level so future changes (e.g. switching to
``TextPositionComparator`` everywhere) don't silently introduce
non-determinism.
"""
from __future__ import annotations

from functools import cmp_to_key

from pypdfbox.cos import COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.text import (
    LineItem,
    PDFTextStripper,
    TextPosition,
    TextPositionComparator,
    WordWithTextPositions,
)


def _tp(text: str = "x", **kw) -> TextPosition:
    base = {"text": text, "x": 0.0, "y": 0.0, "font_size": 12.0, "width": 10.0}
    base.update(kw)
    return TextPosition(**base)


def _page(doc: PDDocument, content: bytes) -> PDPage:
    page = PDPage(PDRectangle(0.0, 0.0, 612.0, 792.0))
    stream = COSStream()
    stream.set_data(content)
    page.set_contents(stream)
    doc.add_page(page)
    return page


# ---------------------------------------------------------------------------
# TextPosition tuple-sort stability
# ---------------------------------------------------------------------------


def test_tuple_sort_stable_for_identical_keys() -> None:
    """``sorted`` is stable: identical sort keys preserve insertion
    order."""
    positions = [
        _tp("a", x=100.0, y=700.0),
        _tp("b", x=100.0, y=700.0),
        _tp("c", x=100.0, y=700.0),
    ]
    s = sorted(positions, key=lambda p: (-p.y, p.x))
    assert [p.text for p in s] == ["a", "b", "c"]


def test_tuple_sort_stable_with_some_unique_keys() -> None:
    """Same line (tied -y) but different x — those get separated by the
    x leg of the key. Distinct y groups are also ordered, and within
    each group ties keep insertion order."""
    positions = [
        # Bottom row (small y).
        _tp("low-a", x=50.0, y=100.0),
        _tp("low-b", x=50.0, y=100.0),  # tied with low-a
        # Top row (large y).
        _tp("high", x=200.0, y=700.0),
    ]
    s = sorted(positions, key=lambda p: (-p.y, p.x))
    assert [p.text for p in s] == ["high", "low-a", "low-b"]


# ---------------------------------------------------------------------------
# TextPositionComparator preserves insertion order for equal-key pairs
# ---------------------------------------------------------------------------


def test_comparator_stable_for_equal_keys() -> None:
    cmp = TextPositionComparator()
    a = _tp("a", x=100.0, y=100.0)
    b = _tp("b", x=100.0, y=100.0)
    c = _tp("c", x=100.0, y=100.0)
    # All three are "equal" per the comparator; sorted output keeps
    # the construction order.
    out = sorted([a, b, c], key=cmp_to_key(cmp))
    assert [p.text for p in out] == ["a", "b", "c"]


def test_comparator_yields_zero_for_equal_positions_pinpoint() -> None:
    cmp = TextPositionComparator()
    a = _tp(x=10.0, y=10.0)
    b = _tp(x=10.0, y=10.0)
    assert cmp(a, b) == 0


# ---------------------------------------------------------------------------
# End-to-end stability through get_text (mirrors test_pdf_text_stripper_options
# but extended to verify three-way ties)
# ---------------------------------------------------------------------------


def test_sort_by_position_stable_for_three_way_y_x_tie() -> None:
    doc = PDDocument()
    _page(
        doc,
        (
            b"BT /F0 12 Tf "
            b"1 0 0 1 100 700 Tm (alpha) Tj "
            b"1 0 0 1 100 700 Tm (beta) Tj "
            b"1 0 0 1 100 700 Tm (gamma) Tj "
            b"ET"
        ),
    )
    s = PDFTextStripper()
    # Even without sort, duplicate-suppression would collapse identical
    # texts; the words differ here so they all survive.
    s.set_sort_by_position(True)
    out = s.get_text(doc)
    # Construction order is preserved despite the sort.
    assert out.index("alpha") < out.index("beta") < out.index("gamma")


# ---------------------------------------------------------------------------
# WordWithTextPositions: identity, equality, ordering preservation when
# packed into a list and sorted by a stable key
# ---------------------------------------------------------------------------


def test_word_with_text_positions_is_not_implicitly_hashed_or_equal() -> None:
    """The data-holder is intentionally a plain class — no
    auto-generated ``__eq__`` / ``__hash__`` — so multiple words with
    the same text are distinct in a set / dict."""
    a = WordWithTextPositions("x", [_tp("x")])
    b = WordWithTextPositions("x", [_tp("x")])
    assert a is not b
    # Default identity equality.
    assert a != b


def test_word_with_text_positions_list_sort_stable() -> None:
    """A list of words sorted by their text payload preserves
    insertion order for ties (identical text strings)."""
    a = WordWithTextPositions("Z", [_tp("Z")])
    b = WordWithTextPositions("A", [_tp("A")])
    c = WordWithTextPositions("A", [_tp("A")])  # tied with b
    sorted_words = sorted([a, b, c], key=lambda w: w.get_text())
    # b and c are ties on "A"; b was inserted first.
    assert sorted_words.index(b) < sorted_words.index(c)
    assert sorted_words[-1] is a


# ---------------------------------------------------------------------------
# LineItem sentinel is not order-affecting in normalize()
# ---------------------------------------------------------------------------


def test_line_item_word_separator_singleton_is_singleton() -> None:
    """The class-level singleton is shared across all callers — sort
    stability would be undermined if every reference were a fresh
    object."""
    a = LineItem.get_word_separator()
    b = LineItem.get_word_separator()
    assert a is b


def test_normalize_preserves_payload_insertion_order_within_word() -> None:
    """Within a word (between two separators), positions are appended
    in the order they appear in the LineItem list."""
    s = PDFTextStripper()
    positions = [_tp(c) for c in "abc"]
    line = [LineItem(p) for p in positions]
    words = s.normalize(line)
    assert len(words) == 1
    word = words[0]
    assert word.get_text() == "abc"
    # The contained TextPositions are in the same order they were given.
    assert word.get_text_positions() == positions


# ---------------------------------------------------------------------------
# Sort stability survives a round-trip through write_string_with_positions
# ---------------------------------------------------------------------------


def test_write_string_with_positions_dispatches_in_input_order() -> None:
    """``write_string_with_positions`` walks ``text_positions`` and
    calls ``process_text_position`` on each in iteration order.
    Capture the visit sequence to confirm."""
    visits: list[str] = []

    class _Capturing(PDFTextStripper):
        def process_text_position(self, text: TextPosition) -> None:
            visits.append(text.text)

    s = _Capturing()
    positions = [_tp(c) for c in "xyz"]
    s.write_string_with_positions("xyz", positions, lambda piece: None)
    assert visits == ["x", "y", "z"]
