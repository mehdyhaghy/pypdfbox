"""Parser for PDF Type 4 functions.

Mirrors upstream
``org.apache.pdfbox.pdmodel.common.function.type4.Parser``. Implements a
small subset of the PostScript language but is no full PostScript
interpreter.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum


class _State(Enum):
    """Used to indicate the parser's current state."""

    NEWLINE = 1
    WHITESPACE = 2
    COMMENT = 3
    TOKEN = 4


class SyntaxHandler(ABC):
    """Defines all possible syntactic elements of a Type 4 function.

    Called by :class:`Parser` as the function is interpreted. Mirrors
    upstream ``Parser.SyntaxHandler`` (a nested interface).
    """

    @abstractmethod
    def new_line(self, text: str) -> None:
        """Indicates that a new line starts.

        :param text: the new line character (CR, LF, CR/LF or FF)
        """

    @abstractmethod
    def whitespace(self, text: str) -> None:
        """Called when whitespace characters are encountered."""

    @abstractmethod
    def token(self, text: str) -> None:
        """Called when a token is encountered.

        No distinction between operators and values is done here.
        """

    @abstractmethod
    def comment(self, text: str) -> None:
        """Called for a comment."""


class AbstractSyntaxHandler(SyntaxHandler):
    """Abstract base class for a :class:`SyntaxHandler` with no-op
    defaults for every callback except :meth:`token`.

    Mirrors upstream ``Parser.AbstractSyntaxHandler``.
    """

    def comment(self, text: str) -> None:  # noqa: D401
        """No-op default."""

    def new_line(self, text: str) -> None:  # noqa: D401
        """No-op default."""

    def whitespace(self, text: str) -> None:  # noqa: D401
        """No-op default."""

    @abstractmethod
    def token(self, text: str) -> None:
        """Subclasses must implement token handling."""


# PostScript control characters (matching upstream Java constants).
_NUL = "\x00"
_EOT = "\x04"
_TAB = "\x09"
_FF = "\x0c"
_CR = "\r"
_LF = "\n"
_SPACE = "\x20"


class Tokenizer:
    """Tokenizer for Type 4 functions.

    Private to :class:`Parser` — mirrors upstream private nested class.
    """

    def __init__(self, text: str, syntax_handler: SyntaxHandler) -> None:
        self._input = text
        self._index = 0
        self._handler = syntax_handler
        self._state = _State.WHITESPACE
        self._buffer: list[str] = []

    def has_more(self) -> bool:
        return self._index < len(self._input)

    def current_char(self) -> str:
        return self._input[self._index]

    def next_char(self) -> str:
        self._index += 1
        if not self.has_more():
            return _EOT
        return self.current_char()

    def peek(self) -> str:
        if self._index < len(self._input) - 1:
            return self._input[self._index + 1]
        return _EOT

    def next_state(self) -> _State:
        ch = self.current_char()
        if ch in (_CR, _LF, _FF):
            self._state = _State.NEWLINE
        elif ch in (_NUL, _TAB, _SPACE):
            self._state = _State.WHITESPACE
        elif ch == "%":
            self._state = _State.COMMENT
        else:
            self._state = _State.TOKEN
        return self._state

    def tokenize(self) -> None:
        while self.has_more():
            self._buffer.clear()
            self.next_state()
            if self._state == _State.NEWLINE:
                self.scan_new_line()
            elif self._state == _State.WHITESPACE:
                self.scan_whitespace()
            elif self._state == _State.COMMENT:
                self.scan_comment()
            else:
                self.scan_token()

    def scan_new_line(self) -> None:
        ch = self.current_char()
        self._buffer.append(ch)
        if ch == _CR and self.peek() == _LF:
            # CRLF is treated as one newline.
            self._buffer.append(self.next_char())
        self._handler.new_line("".join(self._buffer))
        self.next_char()

    def scan_whitespace(self) -> None:
        self._buffer.append(self.current_char())
        while self.has_more():
            ch = self.next_char()
            if ch in (_NUL, _TAB, _SPACE):
                self._buffer.append(ch)
            else:
                break
        self._handler.whitespace("".join(self._buffer))

    def scan_comment(self) -> None:
        self._buffer.append(self.current_char())
        while self.has_more():
            ch = self.next_char()
            if ch in (_CR, _LF, _FF):
                break
            self._buffer.append(ch)
        # EOF reached
        self._handler.comment("".join(self._buffer))

    def scan_token(self) -> None:
        ch = self.current_char()
        self._buffer.append(ch)
        if ch in ("{", "}"):
            self._handler.token("".join(self._buffer))
            self.next_char()
            return
        while self.has_more():
            ch = self.next_char()
            if ch in (_NUL, _TAB, _SPACE, _CR, _LF, _FF, _EOT, "{", "}"):
                break
            self._buffer.append(ch)
        # EOF reached
        self._handler.token("".join(self._buffer))


class Parser:
    """Parser for PDF Type 4 functions.

    Mirrors upstream ``Parser`` (a Java ``final`` class with a private
    constructor and a single static :meth:`parse` entry point). Two
    inner types are exposed as class attributes so callers can write
    ``Parser.SyntaxHandler`` / ``Parser.AbstractSyntaxHandler`` exactly
    like the Java code.
    """

    SyntaxHandler = SyntaxHandler
    AbstractSyntaxHandler = AbstractSyntaxHandler

    def __init__(self) -> None:
        # Private constructor — Java code is ``private Parser() {//nop}``.
        # We allow instantiation in Python (no language-level enforcement)
        # but it serves no purpose; ``parse`` is the only entry point.
        pass

    @staticmethod
    def parse(input: str, handler: SyntaxHandler) -> None:  # noqa: A002 - upstream parameter name
        """Parse a Type 4 function, dispatching syntactic elements to
        ``handler``.

        :param input: the text source
        :param handler: the syntax handler
        """
        tokenizer = Tokenizer(input, handler)
        tokenizer.tokenize()


__all__ = [
    "AbstractSyntaxHandler",
    "Parser",
    "SyntaxHandler",
]
