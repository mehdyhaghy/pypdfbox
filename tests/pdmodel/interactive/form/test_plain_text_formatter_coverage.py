"""Coverage boost for
:mod:`pypdfbox.pdmodel.interactive.form.plain_text_formatter`.

Drives :meth:`PlainTextFormatter.format` and :meth:`process_lines`
through every alignment + wrap-mode combination using a fake content
stream that just records the calls. The formatter only consumes
``PDFont.get_string_width`` and the line-emission methods, so the
fakes can be tiny.
"""

from __future__ import annotations

from typing import Any

from pypdfbox.pdmodel.interactive.form.appearance_style import AppearanceStyle
from pypdfbox.pdmodel.interactive.form.paragraph import Line
from pypdfbox.pdmodel.interactive.form.plain_text import PlainText
from pypdfbox.pdmodel.interactive.form.plain_text_formatter import (
    PlainTextFormatter,
)
from pypdfbox.pdmodel.interactive.form.text_align import TextAlign
from pypdfbox.pdmodel.interactive.form.word import Word


class _FakeFont:
    """Returns one PDF font unit per character."""

    def get_string_width(self, text: str) -> float:
        return float(len(text)) * 100.0


class _RecorderContents:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Any, ...]] = []

    def new_line_at_offset(self, dx: float, dy: float) -> None:
        self.calls.append(("new_line_at_offset", dx, dy))

    def show_text(self, text: str) -> None:
        self.calls.append(("show_text", text))


def _make_style(font_size: float = 12.0) -> AppearanceStyle:
    style = AppearanceStyle()
    style.set_font(_FakeFont())  # type: ignore[arg-type]
    style.set_font_size(font_size)
    return style


def test_format_returns_when_no_text_content() -> None:
    contents = _RecorderContents()
    formatter = (
        PlainTextFormatter.Builder(contents).style(_make_style()).build()
    )
    formatter.format()
    assert contents.calls == []


def test_format_returns_when_no_appearance_style() -> None:
    contents = _RecorderContents()
    formatter = (
        PlainTextFormatter.Builder(contents).text(PlainText("hello")).build()
    )
    formatter.format()
    assert contents.calls == []


def test_format_returns_when_paragraphs_empty() -> None:
    contents = _RecorderContents()

    class _EmptyText:
        def get_paragraphs(self) -> list[Any]:
            return []

    formatter = (
        PlainTextFormatter.Builder(contents)
        .style(_make_style())
        .text(_EmptyText())  # type: ignore[arg-type]
        .build()
    )
    formatter.format()
    assert contents.calls == []


def test_format_no_wrap_left_alignment() -> None:
    contents = _RecorderContents()
    formatter = (
        PlainTextFormatter.Builder(contents)
        .style(_make_style())
        .text(PlainText("hi"))
        .width(1000.0)
        .text_align(TextAlign.LEFT)
        .initial_offset(5.0, 20.0)
        .build()
    )
    formatter.format()
    assert ("show_text", "hi") in contents.calls
    # initial offset applied
    assert contents.calls[0] == ("new_line_at_offset", 5.0, 20.0)


def test_format_no_wrap_center_alignment() -> None:
    contents = _RecorderContents()
    formatter = (
        PlainTextFormatter.Builder(contents)
        .style(_make_style())
        .text(PlainText("ab"))
        .width(1000.0)
        .text_align(TextAlign.CENTER)
        .build()
    )
    formatter.format()
    # Width of "ab" = 2*100*12/1000 = 2.4; centered start = (1000-2.4)/2
    dx, _dy = contents.calls[0][1], contents.calls[0][2]
    assert abs(dx - (1000.0 - 2.4) / 2) < 1e-6


def test_format_no_wrap_right_alignment() -> None:
    contents = _RecorderContents()
    formatter = (
        PlainTextFormatter.Builder(contents)
        .style(_make_style())
        .text(PlainText("ab"))
        .width(1000.0)
        .text_align(TextAlign.RIGHT)
        .build()
    )
    formatter.format()
    dx = contents.calls[0][1]
    assert abs(dx - (1000.0 - 2.4)) < 1e-6


def test_format_no_wrap_line_wider_than_width_starts_at_zero() -> None:
    contents = _RecorderContents()
    formatter = (
        PlainTextFormatter.Builder(contents)
        .style(_make_style())
        .text(PlainText("aaaaaaaaaaaa"))  # very wide
        .width(0.5)  # narrow — line_width >= width
        .text_align(TextAlign.CENTER)
        .build()
    )
    formatter.format()
    # No centering math applied because line_width >= width.
    assert contents.calls[0] == ("new_line_at_offset", 0.0, 0.0)


def _wrapped_word(text: str, width: float) -> Word:
    word = Word(text)
    word.set_attributes({"WIDTH": width})
    return word


def _wrapped_line(words: list[Word]) -> Line:
    line = Line()
    for w in words:
        line.add_word(w)
    line.set_width(sum(float((w.get_attributes() or {}).get("WIDTH", 0)) for w in words))
    return line


def test_process_lines_left_single_paragraph() -> None:
    contents = _RecorderContents()
    formatter = (
        PlainTextFormatter.Builder(contents)
        .style(_make_style())
        .width(100.0)
        .text_align(TextAlign.LEFT)
        .build()
    )
    lines = [_wrapped_line([_wrapped_word("hi", 20.0), _wrapped_word("there", 40.0)])]
    formatter.process_lines(lines, True)
    # First line uses vertical_offset; show_text called per word.
    show_calls = [c for c in contents.calls if c[0] == "show_text"]
    assert [c[1] for c in show_calls] == ["hi", "there"]


def test_process_lines_center_two_lines() -> None:
    contents = _RecorderContents()
    formatter = (
        PlainTextFormatter.Builder(contents)
        .style(_make_style())
        .width(200.0)
        .text_align(TextAlign.CENTER)
        .build()
    )
    lines = [
        _wrapped_line([_wrapped_word("aa", 50.0)]),
        _wrapped_line([_wrapped_word("bb", 80.0)]),
    ]
    formatter.process_lines(lines, True)
    # Two new-line calls for two lines (first uses vertical_offset, second uses -leading).
    line_starts = [c for c in contents.calls if c[0] == "new_line_at_offset"]
    assert len(line_starts) >= 2


def test_process_lines_right_two_lines() -> None:
    contents = _RecorderContents()
    formatter = (
        PlainTextFormatter.Builder(contents)
        .style(_make_style())
        .width(150.0)
        .text_align(TextAlign.RIGHT)
        .build()
    )
    lines = [
        _wrapped_line([_wrapped_word("x", 30.0)]),
        _wrapped_line([_wrapped_word("yz", 60.0)]),
    ]
    formatter.process_lines(lines, True)
    assert any(c[0] == "show_text" and c[1] == "x" for c in contents.calls)
    assert any(c[0] == "show_text" and c[1] == "yz" for c in contents.calls)


def test_process_lines_justify_multi_word_non_last_line() -> None:
    contents = _RecorderContents()
    formatter = (
        PlainTextFormatter.Builder(contents)
        .style(_make_style())
        .width(200.0)
        .text_align(TextAlign.JUSTIFY)
        .build()
    )
    line1 = _wrapped_line(
        [_wrapped_word("aa", 50.0), _wrapped_word("bb", 60.0)]
    )
    line2 = _wrapped_line([_wrapped_word("c", 20.0)])
    formatter.process_lines([line1, line2], True)
    # Inter-word spacing applied between words on the justified line.
    show_calls = [c[1] for c in contents.calls if c[0] == "show_text"]
    assert show_calls == ["aa", "bb", "c"]


def test_process_lines_justify_single_word_skips_spacing() -> None:
    contents = _RecorderContents()
    formatter = (
        PlainTextFormatter.Builder(contents)
        .style(_make_style())
        .width(200.0)
        .text_align(TextAlign.JUSTIFY)
        .build()
    )
    lines = [
        _wrapped_line([_wrapped_word("alone", 70.0)]),
        _wrapped_line([_wrapped_word("end", 40.0)]),
    ]
    formatter.process_lines(lines, True)
    show_calls = [c[1] for c in contents.calls if c[0] == "show_text"]
    assert show_calls == ["alone", "end"]


def test_process_lines_not_first_paragraph_uses_leading_offset() -> None:
    contents = _RecorderContents()
    formatter = (
        PlainTextFormatter.Builder(contents)
        .style(_make_style())
        .width(200.0)
        .text_align(TextAlign.LEFT)
        .build()
    )
    lines = [_wrapped_line([_wrapped_word("x", 20.0)])]
    formatter.process_lines(lines, False)
    # First emission used -leading on the y axis, not vertical_offset.
    first = contents.calls[0]
    assert first[0] == "new_line_at_offset"
    # _DEFAULT_LEADING = 14.4
    assert abs(first[2] - (-14.4)) < 1e-6


def test_format_wrap_lines_drives_process_lines() -> None:
    contents = _RecorderContents()
    formatter = (
        PlainTextFormatter.Builder(contents)
        .style(_make_style())
        .wrap_lines(True)
        .width(500.0)
        .text(PlainText("hello world this is a test"))
        .text_align(TextAlign.LEFT)
        .build()
    )
    formatter.format()
    # Some words have been emitted via show_text.
    show_calls = [c for c in contents.calls if c[0] == "show_text"]
    assert show_calls


def test_format_multi_paragraph_wrap_mode_alternates_first_flag() -> None:
    contents = _RecorderContents()
    formatter = (
        PlainTextFormatter.Builder(contents)
        .style(_make_style())
        .wrap_lines(True)
        .width(500.0)
        .text(PlainText(["one", "two", "three"]))
        .build()
    )
    formatter.format()
    # Each paragraph emits at least one show_text.
    show_count = sum(1 for c in contents.calls if c[0] == "show_text")
    assert show_count >= 3
