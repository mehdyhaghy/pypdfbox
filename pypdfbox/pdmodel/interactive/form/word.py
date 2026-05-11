from __future__ import annotations

from typing import Any


class Word:
    """An individual word — a string which must be kept on the same
    line. Mirrors
    ``org.apache.pdfbox.pdmodel.interactive.form.PlainText.Word``
    (upstream lines 380–404).

    A word carries the raw text content plus an opaque ``attributes``
    payload that upstream stores as a ``java.text.AttributedString``
    pre-populated with the per-word scaled width. The Python port
    stores the attributes payload as ``Any`` (a plain ``dict`` is the
    natural carrier in tests) since :class:`PlainTextFormatter`
    needs only a ``WIDTH`` lookup.
    """

    __slots__ = ("_text", "_attributes")

    def __init__(self, text: str) -> None:
        self._text = text
        self._attributes: Any = None

    def get_text(self) -> str:
        return self._text

    def get_attributes(self) -> Any:
        return self._attributes

    def set_attributes(self, attributes: Any) -> None:
        self._attributes = attributes


__all__ = ["Word"]
