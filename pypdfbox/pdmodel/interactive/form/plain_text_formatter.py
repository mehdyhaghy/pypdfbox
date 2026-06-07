from __future__ import annotations

from typing import TYPE_CHECKING

from .builder import Builder
from .text_align import TextAlign

if TYPE_CHECKING:
    from .appearance_style import AppearanceStyle
    from .paragraph import Line
    from .plain_text import PlainText


_FONT_SCALE = 1000.0


class PlainTextFormatter:
    """Plain-text formatter for AcroForm appearance generation.
    Mirrors
    ``org.apache.pdfbox.pdmodel.interactive.form.PlainTextFormatter``
    (upstream lines 35–289).

    The formatter takes a :class:`PlainText` block and writes the
    corresponding content-stream operators (``newLineAtOffset`` /
    ``showText``) through the bound
    :class:`PDAppearanceContentStream`. Construct via the nested
    :class:`Builder`.
    """

    # Expose Builder + TextAlign as nested classes for upstream parity.
    Builder = Builder

    def __init__(self, builder: Builder) -> None:
        self._appearance_style: AppearanceStyle | None = (
            builder._appearance_style
        )
        self._wrap_lines: bool = builder._wrap_lines
        self._width: float = builder._width
        self._contents = builder._contents
        self._text_content: PlainText | None = builder._text_content
        self._text_alignment: TextAlign = builder._text_alignment
        self._horizontal_offset: float = builder._horizontal_offset
        self._vertical_offset: float = builder._vertical_offset

    def format(self) -> None:
        """Format the text block by emitting content-stream operators
        through the bound contents writer. Mirrors upstream
        ``PlainTextFormatter.format`` (lines 173–219)."""
        if (
            self._text_content is None
            or not self._text_content.get_paragraphs()
        ):
            return
        if self._appearance_style is None:
            return

        is_first_paragraph = True
        for paragraph in self._text_content.get_paragraphs():
            if self._wrap_lines:
                lines = paragraph.get_lines(
                    self._appearance_style.get_font(),
                    self._appearance_style.get_font_size(),
                    self._width,
                )
                self._process_lines(lines, is_first_paragraph)
                is_first_paragraph = False
            else:
                start_offset = 0.0
                line_width = (
                    self._appearance_style.get_font().get_string_width(
                        paragraph.get_text()
                    )
                    * self._appearance_style.get_font_size()
                    / _FONT_SCALE
                )
                if line_width < self._width:
                    if self._text_alignment is TextAlign.CENTER:
                        start_offset = (self._width - line_width) / 2
                    elif self._text_alignment is TextAlign.RIGHT:
                        start_offset = self._width - line_width
                    else:  # LEFT, JUSTIFY
                        start_offset = 0.0
                self._contents.new_line_at_offset(
                    self._horizontal_offset + start_offset,
                    self._vertical_offset,
                )
                self._contents.show_text(paragraph.get_text())

    def process_lines(
        self, lines: list[Line], is_first_paragraph: bool
    ) -> None:
        """Public alias of :meth:`_process_lines` matching upstream's
        ``PlainTextFormatter.processLines`` (Java line 230). Provided
        so call sites ported from PDFBox can keep their original
        method name."""
        self._process_lines(lines, is_first_paragraph)

    def _process_lines(
        self, lines: list[Line], is_first_paragraph: bool
    ) -> None:
        """Process lines for an individual paragraph. Mirrors upstream
        ``processLines`` (lines 230–288)."""
        last_pos = 0.0
        start_offset = 0.0
        inter_word_spacing = 0.0

        for line_index, line in enumerate(lines):
            if self._text_alignment is TextAlign.CENTER:
                start_offset = (self._width - line.get_width()) / 2
            elif self._text_alignment is TextAlign.RIGHT:
                start_offset = self._width - line.get_width()
            elif self._text_alignment is TextAlign.JUSTIFY:
                # Upstream computes inter-word spacing for every non-last
                # line with no word-count guard and never resets it once
                # set (Java processLines lines 248-253). A single-word
                # non-last line therefore divides by ``words.size() - 1 ==
                # 0`` and yields a non-finite value, which the downstream
                # ``new_line_at_offset`` rejects — matching upstream's
                # ``IllegalArgumentException: Infinity is not a finite
                # number`` (pinned as a jar quirk in the oracle test).
                if line_index != len(lines) - 1:
                    inter_word_spacing = line.get_inter_word_spacing(
                        self._width
                    )
            else:
                start_offset = 0.0

            offset = -last_pos + start_offset + self._horizontal_offset

            if line_index == 0 and is_first_paragraph:
                self._contents.new_line_at_offset(
                    offset, self._vertical_offset
                )
            else:
                # keep the last position
                leading = self._appearance_style.get_leading()
                self._vertical_offset = self._vertical_offset - leading
                self._contents.new_line_at_offset(offset, -leading)

            last_pos += offset

            words = line.get_words()
            for word_index, word in enumerate(words):
                self._contents.show_text(word.get_text())
                attrs = word.get_attributes() or {}
                word_width = float(attrs.get("WIDTH", 0.0))
                if word_index != len(words) - 1:
                    self._contents.new_line_at_offset(
                        word_width + inter_word_spacing, 0.0
                    )
                    last_pos = last_pos + word_width + inter_word_spacing

        self._horizontal_offset = self._horizontal_offset - last_pos


# Expose TextAlign as a nested class for upstream parity.
PlainTextFormatter.TextAlign = TextAlign  # type: ignore[attr-defined]


__all__ = ["PlainTextFormatter"]
