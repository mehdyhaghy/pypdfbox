"""Type 2 char-string byte-stream parser.

Mirrors upstream ``org.apache.fontbox.cff.Type2CharStringParser``
(Type2CharStringParser.java:30). Walks a Type 2 char-string byte array
plus its global / local subroutine indexes and emits a list of operands
(``int`` / ``float``) and ``CharStringCommand`` instances - exactly the
upstream ``List<Object>`` shape.

Library-first: charstring **interpretation** (path drawing, hint stem
state, flex variants) is delegated to fontTools elsewhere in the
pypdfbox stack via ``Type2CharString``. This parser only does the
upstream byte-level decoding step plus subroutine unrolling and
hint-mask byte skipping.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from .char_string_command import CharStringCommand
from .type1_keyword import Key
from .type2_keyword import Type2KeyWord

# Mirrors upstream constants (Type2CharStringParser.java:33-38).
_CALLSUBR = Key.CALLSUBR.hash_value
_CALLGSUBR = Key.CALLGSUBR.hash_value
_HINTMASK = Key.HINTMASK.hash_value
_CNTRMASK = Key.CNTRMASK.hash_value


@dataclass
class _GlyphData:
    """Mirrors upstream private inner class ``GlyphData``
    (Type2CharStringParser.java:247)."""

    sequence: list[Any] = field(default_factory=list)
    hstem_count: int = 0
    vstem_count: int = 0


class Type2CharStringParser:
    """Mirrors upstream ``Type2CharStringParser``
    (Type2CharStringParser.java:30)."""

    def __init__(self, font_name: str) -> None:
        self._font_name = font_name

    def parse(
        self,
        bytes_: bytes | bytearray | memoryview,
        global_subr_index: Sequence[bytes | bytearray] | None,
        local_subr_index: Sequence[bytes | bytearray] | None,
        glyph_name: str,  # noqa: ARG002 - upstream takes it for log context
    ) -> list[Any]:
        """Mirrors upstream ``parse(byte[], byte[][], byte[][], String)``
        (Type2CharStringParser.java:63)."""
        glyph_data = _GlyphData()
        gsi = list(global_subr_index) if global_subr_index else []
        lsi = list(local_subr_index) if local_subr_index else []
        self.parse_sequence(bytes(bytes_), gsi, lsi, glyph_data)
        return glyph_data.sequence

    def parse_sequence(
        self,
        data: bytes,
        gsi: list[bytes | bytearray],
        lsi: list[bytes | bytearray],
        glyph_data: _GlyphData,
    ) -> None:
        """Mirrors upstream private ``parseSequence`` (Type2CharStringParser.java:71)."""
        i = 0
        n = len(data)
        while i < n:
            b0 = data[i]
            i += 1
            if b0 == _CALLSUBR:
                self.process_call_subr(gsi, lsi, glyph_data)
            elif b0 == _CALLGSUBR:
                self.process_call_g_subr(gsi, lsi, glyph_data)
            elif b0 in (_HINTMASK, _CNTRMASK):
                glyph_data.vstem_count += (
                    self.count_numbers(glyph_data.sequence) // 2
                )
                mask_length = self.get_mask_length(
                    glyph_data.hstem_count, glyph_data.vstem_count
                )
                # Drop the mask bytes - we don't act on hint masks but
                # have to advance past them. Upstream reads each mask byte
                # via DataInput.readUnsignedByte(), which raises IOException
                # ("End off buffer reached") when the mask runs past the end
                # of the program; mirror that instead of silently advancing.
                if i + mask_length > n:
                    msg = "Truncated Type 2 hint-mask bytes"
                    raise ValueError(msg)
                i += mask_length
                glyph_data.sequence.append(CharStringCommand.get_instance(b0))
            elif (0 <= b0 <= 18) or (21 <= b0 <= 27) or (29 <= b0 <= 31):
                cmd, i = self.read_command(data, i, b0, glyph_data)
                glyph_data.sequence.append(cmd)
            elif b0 == 28 or (32 <= b0 <= 255):
                num, i = self.read_number(data, i, b0)
                glyph_data.sequence.append(num)
            else:  # pragma: no cover - unreachable, b0 is a byte
                msg = f"Invalid Type 2 char string byte {b0:#x}"
                raise ValueError(msg)

    # ---------- subr handling ----------------------------------------------
    def process_call_subr(
        self,
        gsi: list[bytes | bytearray],
        lsi: list[bytes | bytearray],
        glyph_data: _GlyphData,
    ) -> None:
        """Mirrors upstream ``processCallSubr`` (Type2CharStringParser.java:120).

        Upstream only short-circuits when the local subr index is null/empty;
        once it decides to call, it feeds ``getSubrBytes``'s result straight
        into ``processSubr`` with **no** null guard. A malformed operand
        (empty stack, non-integer, or out-of-range subr number) therefore
        propagates as the same kind of runtime error Java raises rather than
        being silently swallowed.
        """
        if lsi:
            subr_bytes = self.get_subr_bytes(lsi, glyph_data)
            self.process_subr(gsi, lsi, subr_bytes, glyph_data)

    def process_call_g_subr(
        self,
        gsi: list[bytes | bytearray],
        lsi: list[bytes | bytearray],
        glyph_data: _GlyphData,
    ) -> None:
        """Mirrors upstream ``processCallGSubr`` (Type2CharStringParser.java:130).

        Like ``process_call_subr``, upstream forwards ``getSubrBytes``'s result
        into ``processSubr`` unconditionally once the global subr index is
        non-empty (no null guard).
        """
        if gsi:
            subr_bytes = self.get_subr_bytes(gsi, glyph_data)
            self.process_subr(gsi, lsi, subr_bytes, glyph_data)

    def process_subr(
        self,
        gsi: list[bytes | bytearray],
        lsi: list[bytes | bytearray],
        subr_bytes: bytes | bytearray | None,
        glyph_data: _GlyphData,
    ) -> None:
        """Mirrors upstream ``processSubr`` (Type2CharStringParser.java:140).

        Upstream takes the raw subr bytes with no null check: an out-of-range
        subr number yields ``null`` from ``getSubrBytes`` and the subsequent
        ``new DataInputByteArray(null)`` / ``hasRemaining()`` throws a
        ``NullPointerException``. We mirror that by letting ``bytes(None)``
        raise ``TypeError`` rather than silently no-op'ing.
        """
        if subr_bytes is None:
            # bytes(None) would raise TypeError("cannot convert 'NoneType' ...")
            # which is the closest analogue to upstream's NullPointerException
            # path; surface it explicitly so the intent is clear.
            msg = "out-of-range subr index resolved to no bytes"
            raise TypeError(msg)
        self.parse_sequence(bytes(subr_bytes), gsi, lsi, glyph_data)
        if glyph_data.sequence:
            last = glyph_data.sequence[-1]
            if (
                isinstance(last, CharStringCommand)
                and last.get_type2_key_word() is Type2KeyWord.RET
            ):
                glyph_data.sequence.pop()

    def get_subr_bytes(
        self,
        subr_index: list[bytes | bytearray],
        glyph_data: _GlyphData,
    ) -> bytes | bytearray | None:
        """Mirrors upstream ``getSubrBytes`` (Type2CharStringParser.java:112).

        Upstream is deliberately unguarded:

        * ``(Integer) sequence.remove(sequence.size() - 1)`` on an empty stack
          calls ``remove(-1)`` -> ``IndexOutOfBoundsException``; we mirror that
          by popping unconditionally so an empty sequence raises ``IndexError``.
        * the cast to ``Integer`` throws ``ClassCastException`` when the popped
          operand is a ``Double`` (the ``255`` 16.16 fixed encoding); we raise
          ``TypeError`` for any non-``int`` operand.
        * ``if (subrNumber < array.length) return array[subrNumber]`` indexes
          with no lower bound, so a negative post-bias subr number throws
          ``ArrayIndexOutOfBoundsException``; we guard ``subr_number < 0``
          explicitly to raise ``IndexError`` (and to avoid Python's silent
          negative-index wrap, which would return the *wrong* subr).
        """
        # remove(size-1) on an empty list raises IndexOutOfBoundsException
        # upstream; pop() on an empty list raises IndexError here.
        operand = glyph_data.sequence.pop()
        if isinstance(operand, bool) or not isinstance(operand, int):
            # Upstream's (Integer) cast throws ClassCastException for a Double
            # operand (e.g. a 255 fixed value left on the stack).
            msg = f"subr operand is not an integer: {operand!r}"
            raise TypeError(msg)
        subr_number = self.calculate_subr_number(operand, len(subr_index))
        if 0 <= subr_number < len(subr_index):
            return subr_index[subr_number]
        if subr_number < 0:
            # Mirror upstream's array[negativeIndex] ->
            # ArrayIndexOutOfBoundsException; never wrap to the list tail.
            msg = f"negative subr index {subr_number}"
            raise IndexError(msg)
        return None

    @staticmethod
    def calculate_subr_number(operand: int, subr_index_length: int) -> int:
        """Mirrors upstream private ``calculateSubrNumber`` (Type2CharStringParser.java:153)."""
        if subr_index_length < 1240:
            return 107 + operand
        if subr_index_length < 33900:
            return 1131 + operand
        return 32768 + operand

    @staticmethod
    def get_mask_length(hstem_count: int, vstem_count: int) -> int:
        """Mirrors upstream ``getMaskLength`` (Type2CharStringParser.java:216)."""
        hint_count = hstem_count + vstem_count
        length = hint_count // 8
        if hint_count % 8 > 0:
            length += 1
        return length

    @staticmethod
    def count_numbers(sequence: list[Any]) -> int:
        """Mirrors upstream ``countNumbers`` (Type2CharStringParser.java:227).
        Counts trailing operands on the sequence."""
        count = 0
        for item in reversed(sequence):
            if not isinstance(item, (int, float)):
                return count
            count += 1
        return count

    # ---------- byte-level readers -----------------------------------------
    def read_command(
        self,
        data: bytes,
        i: int,
        b0: int,
        glyph_data: _GlyphData,
    ) -> tuple[CharStringCommand, int]:
        """Mirrors upstream ``readCommand`` (Type2CharStringParser.java:166)."""
        if b0 in (1, 18):
            glyph_data.hstem_count += self.count_numbers(glyph_data.sequence) // 2
            return CharStringCommand.get_instance(b0), i
        if b0 in (3, 23):
            glyph_data.vstem_count += self.count_numbers(glyph_data.sequence) // 2
            return CharStringCommand.get_instance(b0), i
        if b0 == 12:
            if i >= len(data):
                msg = "Truncated two-byte Type 2 command"
                raise ValueError(msg)
            return CharStringCommand.get_instance(b0, data[i]), i + 1
        return CharStringCommand.get_instance(b0), i

    def read_number(
        self,
        data: bytes,
        i: int,
        b0: int,
    ) -> tuple[int | float, int]:
        """Mirrors upstream ``readNumber`` (Type2CharStringParser.java:186)."""
        if b0 == 28:
            if i + 2 > len(data):
                msg = "Truncated Type 2 short operand"
                raise ValueError(msg)
            value = int.from_bytes(data[i : i + 2], "big", signed=True)
            return value, i + 2
        if 32 <= b0 <= 246:
            return b0 - 139, i
        if 247 <= b0 <= 250:
            if i >= len(data):
                msg = "Truncated Type 2 operand"
                raise ValueError(msg)
            b1 = data[i]
            return (b0 - 247) * 256 + b1 + 108, i + 1
        if 251 <= b0 <= 254:
            if i >= len(data):
                msg = "Truncated Type 2 operand"
                raise ValueError(msg)
            b1 = data[i]
            return -(b0 - 251) * 256 - b1 - 108, i + 1
        if b0 == 255:
            if i + 4 > len(data):
                msg = "Truncated Type 2 fixed operand"
                raise ValueError(msg)
            value = int.from_bytes(data[i : i + 2], "big", signed=True)
            fraction = int.from_bytes(data[i + 2 : i + 4], "big") / 65535.0
            return value + fraction, i + 4
        msg = f"Invalid Type 2 operand byte {b0:#x}"
        raise ValueError(msg)

    def to_string(self) -> str:
        """Mirrors upstream ``toString`` (Type2CharStringParser.java:241)."""
        return self._font_name

    def __str__(self) -> str:
        return self.to_string()


__all__ = ["Type2CharStringParser"]
