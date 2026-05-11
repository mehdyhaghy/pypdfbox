from __future__ import annotations

from typing import TYPE_CHECKING

from .text_align import TextAlign

if TYPE_CHECKING:
    from .appearance_style import AppearanceStyle
    from .plain_text import PlainText
    from .plain_text_formatter import PlainTextFormatter


class Builder:
    """Builder for :class:`PlainTextFormatter`. Mirrors
    ``org.apache.pdfbox.pdmodel.interactive.form.PlainTextFormatter.Builder``
    (upstream lines 83–154).

    The required parameter is the PDAppearanceContentStream the
    formatter writes into (passed positionally); all other parameters
    are optional and chained via the fluent setters.
    """

    def __init__(self, contents: object) -> None:
        # required parameter
        self._contents = contents

        # optional parameters
        self._appearance_style: AppearanceStyle | None = None
        self._wrap_lines: bool = False
        self._width: float = 0.0
        self._text_content: PlainText | None = None
        self._text_alignment: TextAlign = TextAlign.LEFT

        # initial offsets
        self._horizontal_offset: float = 0.0
        self._vertical_offset: float = 0.0

    # ---------- fluent setters ----------

    def style(self, appearance_style: AppearanceStyle) -> Builder:
        self._appearance_style = appearance_style
        return self

    def wrap_lines(self, wrap_lines: bool) -> Builder:
        self._wrap_lines = wrap_lines
        return self

    def width(self, width: float) -> Builder:
        self._width = width
        return self

    def text_align(self, alignment: TextAlign | int) -> Builder:
        if isinstance(alignment, TextAlign):
            self._text_alignment = alignment
        else:
            self._text_alignment = TextAlign.value_of(alignment)
        return self

    def text(self, text_content: PlainText) -> Builder:
        self._text_content = text_content
        return self

    def initial_offset(
        self, horizontal_offset: float, vertical_offset: float
    ) -> Builder:
        self._horizontal_offset = horizontal_offset
        self._vertical_offset = vertical_offset
        return self

    # ---------- build ----------

    def build(self) -> PlainTextFormatter:
        from .plain_text_formatter import PlainTextFormatter

        return PlainTextFormatter(self)


__all__ = ["Builder"]
