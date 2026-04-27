"""Upstream-style parity tests for ``PositionWrapper``.

Apache PDFBox 3.0.x does not ship a standalone ``PositionWrapperTest``;
``PositionWrapper`` is exercised indirectly through
``PDFTextStripper.writePage``. The cases below pin the externally
observable behavior the stripper relies on (default flags off,
``setX()`` only flips on, wrapped position is returned by reference).
"""

from __future__ import annotations

from pypdfbox.text.position_wrapper import PositionWrapper
from pypdfbox.text.text_position import TextPosition


def _wrap() -> PositionWrapper:
    pos = TextPosition(text="x", x=0.0, y=0.0, font_size=12.0, width=6.0)
    return PositionWrapper(pos)


def test_default_line_start_is_false():
    assert _wrap().is_line_start() is False


def test_default_paragraph_start_is_false():
    assert _wrap().is_paragraph_start() is False


def test_default_page_break_is_false():
    assert _wrap().is_page_break() is False


def test_default_hanging_indent_is_false():
    assert _wrap().is_hanging_indent() is False


def test_default_article_start_is_false():
    assert _wrap().is_article_start() is False


def test_set_line_start_turns_flag_on():
    w = _wrap()
    w.set_line_start()
    assert w.is_line_start() is True


def test_set_paragraph_start_turns_flag_on():
    w = _wrap()
    w.set_paragraph_start()
    assert w.is_paragraph_start() is True


def test_set_page_break_turns_flag_on():
    w = _wrap()
    w.set_page_break()
    assert w.is_page_break() is True


def test_set_hanging_indent_turns_flag_on():
    w = _wrap()
    w.set_hanging_indent()
    assert w.is_hanging_indent() is True


def test_set_article_start_turns_flag_on():
    w = _wrap()
    w.set_article_start()
    assert w.is_article_start() is True


def test_get_text_position_returns_constructor_argument():
    pos = TextPosition(text="x", x=1.0, y=2.0, font_size=10.0, width=3.0)
    assert PositionWrapper(pos).get_text_position() is pos
