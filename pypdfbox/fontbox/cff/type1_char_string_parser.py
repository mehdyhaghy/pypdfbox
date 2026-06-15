"""Type 1 char-string byte-stream parser.

Mirrors upstream ``org.apache.fontbox.cff.Type1CharStringParser``
(Type1CharStringParser.java:37). Walks a Type 1 char-string byte array
and emits a list of operands (``int``) and ``CharStringCommand``
instances - exactly the upstream ``List<Object>`` shape.

Library-first: charstring **interpretation** (subroutine recursion,
flex / othersubr semantics) is delegated to fontTools elsewhere in the
pypdfbox stack via ``Type1CharString``. This parser only does the
upstream byte-level decoding step (operand encoding from Adobe Type 1
spec section 6.2 plus the ``callsubr`` / ``callothersubr`` unrolling
that upstream's parser performs before calling the renderer).
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any

from .char_string_command import CharStringCommand
from .type1_keyword import Type1KeyWord

LOG = logging.getLogger(__name__)

# 1-byte command (Type1CharStringParser.java:42).
_CALLSUBR = 10
# 2-byte command prefix (Type1CharStringParser.java:45).
_TWO_BYTE = 12
# Two-byte command suffixes (Type1CharStringParser.java:46-47).
_CALLOTHERSUBR = 16
_POP = 17


class Type1CharStringParser:
    """Mirrors upstream ``Type1CharStringParser``
    (Type1CharStringParser.java:37)."""

    def __init__(self, font_name: str) -> None:
        # Upstream constructor: ``Type1CharStringParser(String fontName)``
        # (Type1CharStringParser.java:57).
        self._font_name = font_name
        self._current_glyph: str | None = None

    def parse(
        self,
        bytes_: bytes | bytearray | memoryview,
        subrs: Sequence[bytes | bytearray],
        glyph_name: str,
    ) -> list[Any]:
        """Mirrors upstream ``parse(byte[], List<byte[]>, String)``
        (Type1CharStringParser.java:71)."""
        self._current_glyph = glyph_name
        return self._parse(bytes(bytes_), list(subrs), [])

    # ---------- internal walk ------------------------------------------------
    def _parse(
        self,
        data: bytes,
        subrs: list[bytes | bytearray],
        sequence: list[Any],
    ) -> list[Any]:
        """Mirrors upstream private ``parse`` recursion
        (Type1CharStringParser.java:77)."""
        i = 0
        n = len(data)
        while i < n:
            b0 = data[i]
            i += 1
            if b0 == _CALLSUBR:
                self.process_call_subr(subrs, sequence)
            elif b0 == _TWO_BYTE and i < n and data[i] == _CALLOTHERSUBR:
                # ``processCallOtherSubr`` expects to peek at the next byte
                # then consume the two-byte sequence; we hand it the read
                # cursor explicitly.
                i = self.process_call_other_subr(data, i, sequence)
            elif 0 <= b0 <= 31:
                cmd, i = self.read_command(data, i, b0)
                sequence.append(cmd)
            elif 32 <= b0 <= 255:
                num, i = self.read_number(data, i, b0)
                sequence.append(num)
            else:  # pragma: no cover - unreachable, b0 is a byte
                msg = f"Invalid Type 1 char string byte {b0:#x}"
                raise ValueError(msg)
        return sequence

    # ---------- subr handling -----------------------------------------------
    def process_call_subr(
        self,
        subrs: list[bytes | bytearray],
        sequence: list[Any],
    ) -> None:
        """Mirrors upstream ``processCallSubr`` (Type1CharStringParser.java:108)."""
        if not sequence:
            return
        obj = sequence.pop()
        if not isinstance(obj, int):
            LOG.warning(
                "Parameter %r for CALLSUBR is ignored, integer expected in "
                "glyph %r of font %s",
                obj, self._current_glyph, self._font_name,
            )
            return
        operand = obj
        if 0 <= operand < len(subrs):
            subr_bytes = subrs[operand]
            self._parse(bytes(subr_bytes), subrs, sequence)
            if sequence:
                last = sequence[-1]
                if (
                    isinstance(last, CharStringCommand)
                    and last.get_type1_key_word() is Type1KeyWord.RET
                ):
                    sequence.pop()
        else:
            LOG.warning(
                "CALLSUBR is ignored, operand: %d, subrs.size(): %d in "
                "glyph %r of font %s",
                operand, len(subrs), self._current_glyph, self._font_name,
            )
            while sequence and isinstance(sequence[-1], int):
                sequence.pop()

    def process_call_other_subr(
        self,
        data: bytes,
        i: int,
        sequence: list[Any],
    ) -> int:
        """Mirrors upstream ``processCallOtherSubr``
        (Type1CharStringParser.java:143). Returns the new read cursor."""
        # Consume the CALLOTHERSUBR byte (peeked at).
        i += 1
        if len(sequence) < 2:
            return i
        othersubr_num = sequence.pop()
        num_args = sequence.pop()
        if not isinstance(othersubr_num, int) or not isinstance(num_args, int):
            return i

        results: list[int] = []  # used as a deque with push/pop
        if othersubr_num == 0:
            # End flex.
            results.append(self.remove_integer(sequence))
            results.append(self.remove_integer(sequence))
            if sequence:
                sequence.pop()
            sequence.append(0)
            sequence.append(CharStringCommand.COMMAND_CALLOTHERSUBR)
        elif othersubr_num == 1:
            # Begin flex.
            sequence.append(1)
            sequence.append(CharStringCommand.COMMAND_CALLOTHERSUBR)
        elif othersubr_num == 3:
            # Allows hint replacement.
            results.append(self.remove_integer(sequence))
        else:
            for _ in range(num_args):
                results.append(self.remove_integer(sequence))

        # Pop must follow immediately (Type1CharStringParser.java:182).
        #
        # Upstream peeks ``input.peekUnsignedByte(0)`` then
        # ``peekUnsignedByte(1)`` unconditionally; ``DataInputByteArray``
        # raises ``IOException`` (-> ``OSError`` here) when either offset
        # is past the end of the buffer (DataInputByteArray.java:126). A
        # truncated charstring whose ``callothersubr`` is not followed by
        # the bytes the pop-peek needs therefore throws, rather than
        # silently exiting the loop. We mirror that EOF-throws contract
        # via ``_peek_unsigned_byte`` instead of guarding with a bounds
        # check (which would swallow the upstream error).
        while (
            self._peek_unsigned_byte(data, i) == _TWO_BYTE
            and self._peek_unsigned_byte(data, i + 1) == _POP
        ):
            i += 2
            if results:
                sequence.append(results.pop())

        if results:
            LOG.warning(
                "Value left on the PostScript stack in glyph %r of font %s",
                self._current_glyph, self._font_name,
            )
        return i

    @staticmethod
    def remove_integer(sequence: list[Any]) -> int:
        """Mirrors upstream private ``removeInteger`` (Type1CharStringParser.java:198)."""
        if not sequence:
            msg = "Empty stack while reading othersubr operand"
            raise OSError(msg)
        item = sequence.pop()
        if isinstance(item, int):
            return item
        if (
            isinstance(item, CharStringCommand)
            and item.get_type1_key_word() is Type1KeyWord.DIV
        ):
            if len(sequence) < 2:
                msg = "DIV with insufficient operands"
                raise OSError(msg)
            a = sequence.pop()
            b = sequence.pop()
            if not isinstance(a, int) or not isinstance(b, int):
                msg = "DIV operands are not integers"
                raise OSError(msg)
            return b // a
        msg = f"Unexpected char string command: {item}"
        raise OSError(msg)

    # ---------- byte-level readers -----------------------------------------
    @staticmethod
    def _peek_unsigned_byte(data: bytes, offset: int) -> int:
        """Mirror upstream ``DataInputByteArray.peekUnsignedByte``
        (DataInputByteArray.java:120). A negative offset or an offset at /
        past the end of the buffer raises ``OSError`` (upstream's
        ``IOException``); otherwise returns the unsigned byte. The
        ``callothersubr`` pop-peel loop relies on this throwing at EOF so
        a truncated charstring matches upstream rather than silently
        ending the loop."""
        if offset < 0:
            msg = "offset is negative"
            raise OSError(msg)
        if offset >= len(data):
            msg = f"Offset position is out of range {offset} >= {len(data)}"
            raise OSError(msg)
        return data[offset]

    def read_command(
        self, data: bytes, i: int, b0: int
    ) -> tuple[CharStringCommand, int]:
        """Mirrors upstream ``readCommand`` (Type1CharStringParser.java:217).

        The two-byte escape reads its second byte through
        ``readUnsignedByte``, which throws ``IOException`` (-> ``OSError``)
        on a truncated buffer (DataInputByteArray.java:103)."""
        if b0 == 12:
            if i >= len(data):
                msg = "End off buffer reached"
                raise OSError(msg)
            b1 = data[i]
            return CharStringCommand.get_instance(b0, b1), i + 1
        return CharStringCommand.get_instance(b0), i

    def read_number(
        self, data: bytes, i: int, b0: int
    ) -> tuple[int, int]:
        """Mirrors upstream ``readNumber`` (Type1CharStringParser.java:227).

        Operand follow-up bytes are read through ``readUnsignedByte`` /
        ``readInt``, which raise ``IOException`` (-> ``OSError``) when the
        buffer is exhausted mid-operand (DataInputByteArray.java:103)."""
        if 32 <= b0 <= 246:
            return b0 - 139, i
        if 247 <= b0 <= 250:
            if i >= len(data):
                msg = "End off buffer reached"
                raise OSError(msg)
            b1 = data[i]
            return (b0 - 247) * 256 + b1 + 108, i + 1
        if 251 <= b0 <= 254:
            if i >= len(data):
                msg = "End off buffer reached"
                raise OSError(msg)
            b1 = data[i]
            return -(b0 - 251) * 256 - b1 - 108, i + 1
        if b0 == 255:
            if i + 4 > len(data):
                msg = "End off buffer reached"
                raise OSError(msg)
            value = int.from_bytes(data[i : i + 4], "big", signed=True)
            return value, i + 4
        # Upstream throws ``IllegalArgumentException`` here
        # (Type1CharStringParser.java:249) -> ``ValueError``.
        msg = f"Invalid Type 1 operand byte {b0:#x}"
        raise ValueError(msg)


__all__ = ["Type1CharStringParser"]
