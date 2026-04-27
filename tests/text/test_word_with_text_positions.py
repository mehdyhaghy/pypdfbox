from __future__ import annotations

from pypdfbox.text import TextPosition, WordWithTextPositions


def _tp(text: str, x: float = 0.0, y: float = 0.0) -> TextPosition:
    return TextPosition(text=text, x=x, y=y, font_size=12.0)


def test_get_text_returns_constructor_argument() -> None:
    word = WordWithTextPositions("hello", [_tp("h"), _tp("e")])
    assert word.get_text() == "hello"


def test_get_text_positions_returns_constructor_argument() -> None:
    positions = [_tp("h"), _tp("e"), _tp("l"), _tp("l"), _tp("o")]
    word = WordWithTextPositions("hello", positions)
    assert word.get_text_positions() is positions


def test_text_attribute_matches_accessor() -> None:
    word = WordWithTextPositions("foo", [_tp("f"), _tp("o"), _tp("o")])
    assert word.text == word.get_text()
    assert word.text_positions is word.get_text_positions()


def test_empty_text_and_empty_positions_are_allowed() -> None:
    word = WordWithTextPositions("", [])
    assert word.get_text() == ""
    assert word.get_text_positions() == []


def test_text_length_may_differ_from_position_count() -> None:
    # Upstream docstring notes that normalization may collapse glyphs;
    # the data holder must accept mismatched lengths without complaint.
    positions = [_tp("e"), _tp("́")]  # combining acute
    word = WordWithTextPositions("é", positions)  # composed "é"
    assert len(word.get_text()) == 1
    assert len(word.get_text_positions()) == 2


def test_positions_list_is_shared_not_copied() -> None:
    positions: list[TextPosition] = [_tp("x")]
    word = WordWithTextPositions("x", positions)
    positions.append(_tp("y"))
    assert word.get_text_positions() == positions
    assert len(word.get_text_positions()) == 2
