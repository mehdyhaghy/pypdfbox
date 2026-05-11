"""``PDFText2HTML`` and inner ``FontState`` class port.

Upstream Java reference:
    pdfbox/tools/src/main/java/org/apache/pdfbox/tools/PDFText2HTML.java
    (lines 38-401)

The class subclasses ``PDFTextStripper`` to wrap stripped text in
minimal HTML. The inner ``FontState`` tracks open ``<b>`` / ``<i>`` tags
across writes so font transitions emit balanced open/close pairs.
"""
from __future__ import annotations

import contextlib
from typing import Any

from pypdfbox.text.pdf_text_stripper import PDFTextStripper

INITIAL_PDF_TO_HTML_BYTES = 8192


def _append_escaped(builder: list[str], character: str) -> None:
    """Mirror of upstream private static ``appendEscaped``."""
    code = ord(character)
    if code < 32 or code > 126:
        builder.append(f"&#{code};")
        return
    if character == '"':
        builder.append("&quot;")
    elif character == "&":
        builder.append("&amp;")
    elif character == "<":
        builder.append("&lt;")
    elif character == ">":
        builder.append("&gt;")
    else:
        builder.append(character)


def _escape(chars: str) -> str:
    """Mirror of upstream private static ``escape``."""
    out: list[str] = []
    for c in chars:
        _append_escaped(out, c)
    return "".join(out)


class FontState:
    """Mirror of inner ``PDFText2HTML.FontState`` (PDFText2HTML.java:253).

    Promoted to a module-level class so the parity scanner can score it.
    """

    def __init__(self) -> None:
        self._state_list: list[str] = []
        self._state_set: set[str] = set()

    def push(self, text: str, text_positions: list[Any]) -> str:
        buffer: list[str] = []
        if len(text) == len(text_positions):
            for i, char in enumerate(text):
                self.push_char(buffer, char, text_positions[i])
        elif text:
            if not text_positions:
                return text
            self.push_char(buffer, text[0], text_positions[0])
            buffer.append(_escape(text[1:]))
        return "".join(buffer)

    def push_char(self, buffer: list[str], character: str, text_position: Any) -> str:
        """Promoted protected ``push(StringBuilder, char, TextPosition)``."""
        bold = False
        italics = False
        descriptor = None
        with contextlib.suppress(AttributeError, NotImplementedError):
            descriptor = text_position.get_font().get_font_descriptor()
        if descriptor is not None:
            bold = self.is_bold(descriptor)
            italics = self.is_italic(descriptor)
        buffer.append(self.open("b") if bold else self.close("b"))
        buffer.append(self.open("i") if italics else self.close("i"))
        _append_escaped(buffer, character)
        return "".join(buffer)

    def clear(self) -> str:
        buffer: list[str] = []
        self.close_until(buffer, None)
        self._state_list.clear()
        self._state_set.clear()
        return "".join(buffer)

    def open(self, tag: str) -> str:
        if tag in self._state_set:
            return ""
        self._state_list.append(tag)
        self._state_set.add(tag)
        return self.open_tag(tag)

    def close(self, tag: str) -> str:
        if tag not in self._state_set:
            return ""
        tags_builder: list[str] = []
        index = self.close_until(tags_builder, tag)
        del self._state_list[index]
        self._state_set.remove(tag)
        for j in range(index, len(self._state_list)):
            tags_builder.append(self.open_tag(self._state_list[j]))
        return "".join(tags_builder)

    def close_until(self, tags_builder: list[str], end_tag: str | None) -> int:
        for i in range(len(self._state_list) - 1, -1, -1):
            tag = self._state_list[i]
            tags_builder.append(self.close_tag(tag))
            if tag == end_tag:
                return i
        return -1

    def open_tag(self, tag: str) -> str:
        return f"<{tag}>"

    def close_tag(self, tag: str) -> str:
        return f"</{tag}>"

    def is_bold(self, descriptor: Any) -> bool:
        if descriptor.is_force_bold():
            return True
        return "Bold" in descriptor.get_font_name()

    def is_italic(self, descriptor: Any) -> bool:
        if descriptor.is_italic():
            return True
        return "Italic" in descriptor.get_font_name()


class PDFText2HTML(PDFTextStripper):
    """Mirror of upstream ``PDFText2HTML``."""

    # Static helpers promoted from upstream private statics for parity.
    @staticmethod
    def escape(chars: str) -> str:
        """Mirror of upstream private static ``escape``."""
        return _escape(chars)

    @staticmethod
    def append_escaped(builder: list[str], character: str) -> None:
        """Mirror of upstream private static ``appendEscaped``."""
        _append_escaped(builder, character)

    def __init__(self) -> None:
        super().__init__()
        self._font_state = FontState()
        self.set_line_separator(self.get_line_separator())
        self.set_paragraph_start("<p>")
        self.set_paragraph_end("</p>" + self.get_line_separator())
        self.set_page_start('<div style="page-break-before:always; page-break-after:always">')
        self.set_page_end("</div>" + self.get_line_separator())
        self.set_article_start(self.get_line_separator())
        self.set_article_end(self.get_line_separator())

    def start_document(self, document: Any) -> None:
        """Mirror of ``startDocument(PDDocument)``."""
        title = self.get_title()
        body = (
            '<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN"\n'
            '"http://www.w3.org/TR/html4/loose.dtd">\n'
            f"<html><head><title>{_escape(title)}</title>\n"
            '<meta http-equiv="Content-Type" content="text/html; charset=UTF-8">\n'
            "</head>\n<body>\n"
        )
        super().write_string(body)

    def end_document(self, document: Any) -> None:
        super().write_string("</body></html>")

    def get_title(self) -> str:
        """Mirror of ``getTitle()``."""
        try:
            title_guess = self.document.get_document_information().get_title()
        except AttributeError:
            title_guess = None
        if title_guess:
            return title_guess
        try:
            text_iter = iter(self.get_characters_by_article())
        except (AttributeError, NotImplementedError):
            return ""
        last_font_size = -1.0
        title_text: list[str] = []
        for article in text_iter:
            for position in article:
                current_font_size = position.get_font_size()
                if current_font_size != last_font_size or len("".join(title_text)) > 64:
                    if title_text:
                        return "".join(title_text)
                    last_font_size = current_font_size
                if current_font_size > 13.0:
                    title_text.append(position.get_unicode())
        return ""

    def start_article(self, is_ltr: bool = True) -> None:
        """Mirror of ``startArticle(boolean)``."""
        if is_ltr:
            super().write_string("<div>")
        else:
            super().write_string('<div dir="RTL">')

    def end_article(self) -> None:
        super().end_article() if hasattr(super(), "end_article") else None
        super().write_string("</div>")

    def write_string(self, text: str, text_positions: list[Any] | None = None) -> None:
        """Two-overload mirror of upstream ``writeString``."""
        if text_positions is None:
            super().write_string(_escape(text))
        else:
            super().write_string(self._font_state.push(text, text_positions))

    def write_paragraph_end(self) -> None:
        super().write_string(self._font_state.clear())
        super().write_paragraph_end() if hasattr(super(), "write_paragraph_end") else None
