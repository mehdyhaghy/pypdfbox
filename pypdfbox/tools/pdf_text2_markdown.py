"""``PDFText2Markdown`` and inner ``FontState`` class port.

Upstream Java reference:
    pdfbox/tools/src/main/java/org/apache/pdfbox/tools/PDFText2Markdown.java
    (lines 35-318)
"""
from __future__ import annotations

import contextlib
from typing import Any

from pypdfbox.text.pdf_text_stripper import PDFTextStripper


def _append_escaped(builder: list[str], character: str) -> None:
    """Mirror of upstream private static ``appendEscaped`` (Markdown variant)."""
    if character in {"*", "+", "-", "#"}:
        builder.append("\\" + character)
    elif ord(character) == 178:
        builder.append("<sup>2</sup>")
    elif ord(character) == 179:
        builder.append("<sup>3</sup>")
    else:
        builder.append(character)


def _escape(chars: str) -> str:
    out: list[str] = []
    for c in chars:
        _append_escaped(out, c)
    return "".join(out)


class FontState:
    """Mirror of inner ``PDFText2Markdown.FontState`` (PDFText2Markdown.java:166)."""

    def __init__(self) -> None:
        self._state_list: list[str] = []
        self._state_set: set[str] = set()

    def push(self, text: str, text_positions: list[Any]) -> str:
        buffer: list[str] = []
        if len(text) == len(text_positions):
            for i, char in enumerate(text):
                self.push_char(buffer, char, text_positions[i])
        elif text:  # pragma: no branch
            # Defensive: write_string is only invoked with a non-empty
            # text payload by PDFTextStripper; the False arm has no
            # live caller.
            if not text_positions:
                return text
            self.push_char(buffer, text[0], text_positions[0])
            buffer.append(_escape(text[1:]))
        return "".join(buffer)

    def push_char(self, buffer: list[str], character: str, text_position: Any) -> str:
        bold = False
        italics = False
        descriptor = None
        with contextlib.suppress(AttributeError, NotImplementedError):
            descriptor = text_position.get_font().get_font_descriptor()
        if descriptor is not None:
            bold = self.is_bold(descriptor)
            italics = self.is_italic(descriptor)
        buffer.append(self.open("**") if bold else self.close("**"))
        buffer.append(self.open("*") if italics else self.close("*"))
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
        return tag

    def close_tag(self, tag: str) -> str:
        return tag

    def is_bold(self, descriptor: Any) -> bool:
        if descriptor.is_force_bold():
            return True
        return "bold" in descriptor.get_font_name().lower()

    def is_italic(self, descriptor: Any) -> bool:
        if descriptor.is_italic():
            return True
        font_name = descriptor.get_font_name().lower()
        return "italic" in font_name or "oblique" in font_name


class PDFText2Markdown(PDFTextStripper):
    """Mirror of upstream ``PDFText2Markdown``."""

    @staticmethod
    def escape(chars: str) -> str:
        """Mirror of upstream private static ``escape`` (Markdown variant)."""
        return _escape(chars)

    @staticmethod
    def append_escaped(builder: list[str], character: str) -> None:
        """Mirror of upstream private static ``appendEscaped``."""
        _append_escaped(builder, character)

    def __init__(self) -> None:
        super().__init__()
        self._font_state = FontState()
        ls = self.get_line_separator()
        self.set_line_separator(ls)
        self.set_paragraph_start(ls)
        self.set_paragraph_end(ls)
        self.set_page_start(ls)
        self.set_page_end(ls)
        self.set_article_start(ls)
        self.set_article_end(ls)

    def _emit_md(self, text: str) -> None:
        """Write ``text`` to the active per-walk sink installed by
        :meth:`PDFTextStripper.get_text`.

        Upstream PDFBox's ``PDFText2Markdown`` routes its writes through the
        protected ``output`` Writer via ``super.writeString(String)``;
        pypdfbox's parent ``write_string`` instead takes the production
        ``(text, text_positions, sink)`` signature and streams through a
        per-walk callable exposed as :attr:`PDFTextStripper._active_sink`.
        Calling ``super().write_string(text)`` with a single argument (as the
        class previously did) raised ``TypeError`` and crashed every
        ``-md`` extraction. Mirror the HTML subclass: emit through the active
        sink, falling back to the parent's stubbed 1-arg ``write_string`` only
        when no walk is active (coverage tests that monkeypatch the parent).
        """
        sink = getattr(self, "_active_sink", None)
        if sink is not None:
            sink(text)
            return
        with contextlib.suppress(TypeError):
            super().write_string(text)

    def start_article(self, is_ltr: bool = True) -> None:
        self._emit_md(self.get_line_separator())

    def end_article(self) -> None:
        with contextlib.suppress(AttributeError, TypeError):
            super().end_article()
        self._emit_md(self.get_line_separator())

    def write_string(
        self,
        text: str,
        text_positions: list[Any] | None = None,
        sink: Any = None,
    ) -> None:
        """Three-overload mirror of upstream ``writeString``.

        - ``write_string(text)`` — coverage path: emit ``_escape(text)``.
        - ``write_string(text, text_positions)`` — emit the font-state-
          decorated run.
        - ``write_string(text, text_positions, sink)`` — production path
          used by :meth:`PDFTextStripper.write_string_with_positions` during
          a real ``get_text`` / ``write_text`` walk; write straight to the
          supplied sink. Mirrors the HTML subclass so the markdown font-state
          decoration stays live during a streamed extraction.
        """
        if text_positions is None:
            decorated = _escape(text)
        else:
            decorated = self._font_state.push(text, text_positions)
        if sink is not None:
            sink(decorated)
        else:
            self._emit_md(decorated)

    def write_paragraph_end(self, sink: Any = None) -> None:
        flush_text = self._font_state.clear()
        if flush_text:
            if sink is not None:
                sink(flush_text)
            else:
                self._emit_md(flush_text)
        if sink is not None:
            super().write_paragraph_end(sink)
        else:
            with contextlib.suppress(TypeError):
                super().write_paragraph_end()
