"""Lexical token from a Type 1 font lexer.

Mirrors ``org.apache.fontbox.type1.Token`` (PDFBox 3.0,
``fontbox/src/main/java/org/apache/fontbox/type1/Token.java``).
"""

from __future__ import annotations

from enum import Enum


class Kind(Enum):
    NONE = "NONE"
    STRING = "STRING"
    NAME = "NAME"
    LITERAL = "LITERAL"
    REAL = "REAL"
    INTEGER = "INTEGER"
    START_ARRAY = "START_ARRAY"
    END_ARRAY = "END_ARRAY"
    START_PROC = "START_PROC"
    END_PROC = "END_PROC"
    START_DICT = "START_DICT"
    END_DICT = "END_DICT"
    CHARSTRING = "CHARSTRING"


class Token:
    """A single lexical token emitted by the Type 1 lexer."""

    # Kind aliases that mirror the upstream static fields.
    NONE = Kind.NONE
    STRING = Kind.STRING
    NAME = Kind.NAME
    LITERAL = Kind.LITERAL
    REAL = Kind.REAL
    INTEGER = Kind.INTEGER
    START_ARRAY = Kind.START_ARRAY
    END_ARRAY = Kind.END_ARRAY
    START_PROC = Kind.START_PROC
    END_PROC = Kind.END_PROC
    START_DICT = Kind.START_DICT
    END_DICT = Kind.END_DICT
    CHARSTRING = Kind.CHARSTRING

    Kind = Kind

    def __init__(self, value: str | bytes | bytearray | int, kind: Kind) -> None:
        self._kind = kind
        self._text: str | None
        self._data: bytes | None
        if isinstance(value, (bytes, bytearray)):
            self._text = None
            self._data = bytes(value)
        else:
            self._text = str(value) if not isinstance(value, str) else value
            self._data = None

    def get_text(self) -> str | None:
        return self._text

    def get_kind(self) -> Kind:
        return self._kind

    def int_value(self) -> int:
        # Upstream parses as float first to tolerate "1.0" where an int is expected.
        return int(float(self._text or "0"))

    def float_value(self) -> float:
        return float(self._text or "0")

    def boolean_value(self) -> bool:
        return self._text == "true"

    def get_data(self) -> bytes | None:
        return self._data

    def to_string(self) -> str:
        """Mirror upstream ``Token.toString``."""
        if self._kind is Kind.CHARSTRING:
            length = 0 if self._data is None else len(self._data)
            return f"Token[kind=CHARSTRING, data={length} bytes]"
        return f"Token[kind={self._kind.name}, text={self._text}]"

    def __repr__(self) -> str:
        return self.to_string()


__all__ = ["Token", "Kind"]
