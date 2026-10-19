"""A bounds-checked cursor over a TrueType bytecode program.

The program may be the fpgm, prep, a glyph instruction stream, or a function
body. The stream owns the program counter so individual opcode handlers never
index the array by hand, which removes a whole class of off-by-one and overrun
bugs. Reads past the end raise :class:`HintingException` so the per-glyph
fallback can catch cleanly.

The interpreter's dispatch loop and push/skip handlers read the slots
directly for speed; they apply the same bounds rules as the methods here.
"""

from __future__ import annotations

from collections.abc import Iterable

from pypdfbox.fontbox.ttf.hinting_exception import HintingException


class BytecodeStream:
    """Mirrors upstream package-private ``BytecodeStream``."""

    __slots__ = ("_code", "_instruction_start", "_ip", "_limit")

    def __init__(self, code: bytes | bytearray | Iterable[int] | None) -> None:
        """Wraps ``code`` (not copied when it is ``bytes``/``bytearray``).

        A sequence of 0-255 ints (such as ``GlyphDescription.get_instructions``
        returns) is converted to ``bytes`` once.
        """
        if code is None:
            code = b""
        elif not isinstance(code, (bytes, bytearray)):
            code = bytes(code)
        self._code = code
        self._ip = 0
        self._instruction_start = 0
        # exclusive upper bound for the program counter; a function body ends at its ENDF
        self._limit = len(code)

    def get_code(self) -> bytes | bytearray:
        """Returns the underlying bytecode (not copied); used to record function entry points."""
        return self._code

    def has_next(self) -> bool:
        """Returns true if there is at least one more byte to read."""
        return self._ip < self._limit

    def set_end(self, end: int) -> None:
        """Restricts execution to ``[0, end]``.

        The stream is exhausted after the byte at ``end`` (the ``ENDF`` of a
        function body) and a seek past it is an error, as a jump out of a
        function body is in FreeType.
        """
        self._limit = min(len(self._code), end + 1)

    def position(self) -> int:
        """Returns the current program-counter position."""
        return self._ip

    def mark_instruction_start(self) -> None:
        """Records the current position as the start of the instruction about to be read.

        Relative jumps (``JMPR``/``JROT``/``JROF``) are measured from here.
        """
        self._instruction_start = self._ip

    def instruction_start(self) -> int:
        """Returns the position recorded by the most recent :meth:`mark_instruction_start`."""
        return self._instruction_start

    def seek(self, position: int) -> None:
        """Moves the program counter to an absolute position within ``[0, limit]``."""
        if position < 0 or position > self._limit:
            raise HintingException(f"bytecode seek out of range: {position} of {self._limit}")
        self._ip = position

    def skip(self, delta: int) -> None:
        """Advances the program counter by a relative amount (may be negative)."""
        self.seek(self._ip + delta)

    def next_byte(self) -> int:
        """Reads the next byte as an unsigned 0-255 value (an opcode, or push operand).

        Like :meth:`seek`, reads honour a function body's end, so a push
        reached by a jump into the middle of another push's operands cannot
        take bytes past the body's ``ENDF``.
        """
        ip = self._ip
        if ip >= self._limit:
            raise HintingException(f"bytecode read past end at {ip}")
        self._ip = ip + 1
        return self._code[ip]

    def next_word(self) -> int:
        """Reads the next two bytes as a signed big-endian 16-bit word."""
        ip = self._ip
        if ip + 1 >= self._limit:
            raise HintingException(f"bytecode word read past end at {ip}")
        code = self._code
        self._ip = ip + 2
        value = (code[ip] << 8) | code[ip + 1]
        return value - 0x10000 if value & 0x8000 else value


__all__ = ["BytecodeStream"]
