from __future__ import annotations

from pypdfbox.text.position_wrapper import PositionWrapper
from pypdfbox.text.text_position import TextPosition


def _make_position() -> TextPosition:
    return TextPosition(
        text="Hello", x=10.0, y=20.0, font_size=12.0, width=50.0
    )


def test_get_text_position_returns_wrapped_value():
    pos = _make_position()
    wrapper = PositionWrapper(pos)
    assert wrapper.get_text_position() is pos


def test_default_flags_are_false():
    wrapper = PositionWrapper(_make_position())
    assert wrapper.is_line_start() is False
    assert wrapper.is_paragraph_start() is False
    assert wrapper.is_page_break() is False
    assert wrapper.is_hanging_indent() is False
    assert wrapper.is_article_start() is False


def test_set_line_start_flips_only_that_flag():
    wrapper = PositionWrapper(_make_position())
    wrapper.set_line_start()
    assert wrapper.is_line_start() is True
    assert wrapper.is_paragraph_start() is False
    assert wrapper.is_page_break() is False
    assert wrapper.is_hanging_indent() is False
    assert wrapper.is_article_start() is False


def test_set_paragraph_start_flips_only_that_flag():
    wrapper = PositionWrapper(_make_position())
    wrapper.set_paragraph_start()
    assert wrapper.is_paragraph_start() is True
    assert wrapper.is_line_start() is False
    assert wrapper.is_page_break() is False
    assert wrapper.is_hanging_indent() is False
    assert wrapper.is_article_start() is False


def test_set_page_break_flips_only_that_flag():
    wrapper = PositionWrapper(_make_position())
    wrapper.set_page_break()
    assert wrapper.is_page_break() is True
    assert wrapper.is_line_start() is False
    assert wrapper.is_paragraph_start() is False
    assert wrapper.is_hanging_indent() is False
    assert wrapper.is_article_start() is False


def test_set_hanging_indent_flips_only_that_flag():
    wrapper = PositionWrapper(_make_position())
    wrapper.set_hanging_indent()
    assert wrapper.is_hanging_indent() is True
    assert wrapper.is_line_start() is False
    assert wrapper.is_paragraph_start() is False
    assert wrapper.is_page_break() is False
    assert wrapper.is_article_start() is False


def test_set_article_start_flips_only_that_flag():
    wrapper = PositionWrapper(_make_position())
    wrapper.set_article_start()
    assert wrapper.is_article_start() is True
    assert wrapper.is_line_start() is False
    assert wrapper.is_paragraph_start() is False
    assert wrapper.is_page_break() is False
    assert wrapper.is_hanging_indent() is False


def test_setters_are_idempotent():
    wrapper = PositionWrapper(_make_position())
    wrapper.set_line_start()
    wrapper.set_line_start()
    assert wrapper.is_line_start() is True


def test_all_flags_can_be_set_independently():
    wrapper = PositionWrapper(_make_position())
    wrapper.set_line_start()
    wrapper.set_paragraph_start()
    wrapper.set_page_break()
    wrapper.set_hanging_indent()
    wrapper.set_article_start()
    assert wrapper.is_line_start() is True
    assert wrapper.is_paragraph_start() is True
    assert wrapper.is_page_break() is True
    assert wrapper.is_hanging_indent() is True
    assert wrapper.is_article_start() is True


def test_wrapper_uses_slots():
    wrapper = PositionWrapper(_make_position())
    # __slots__ should prevent arbitrary attribute assignment.
    import pytest

    with pytest.raises(AttributeError):
        wrapper.foo = "bar"  # type: ignore[attr-defined]
