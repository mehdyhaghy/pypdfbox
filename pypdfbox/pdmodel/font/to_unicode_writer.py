"""Writes ToUnicode CMap streams.

Mirrors ``org.apache.pdfbox.pdmodel.font.ToUnicodeWriter`` (PDFBox 3.0,
``pdfbox/src/main/java/org/apache/pdfbox/pdmodel/font/ToUnicodeWriter.java``
lines 36-228).

A ToUnicode CMap maps CIDs to their Unicode equivalents — used by every
PDF text extractor to recover the original text from a font that is
indexed by CID. This writer accumulates ``(cid, text)`` pairs, then
emits an ASCII-encoded CMap stream that can be assigned to the
``/ToUnicode`` entry of a PDF font dictionary.

The writer optimises by collapsing consecutive CID -> Unicode mappings
into ``beginbfrange`` ranges where allowed by Adobe spec §5.9, example
5.16 (sequential CIDs differing only in the low-order byte mapping to
sequential code points differing only in the low-order byte).

Mapping batches are limited to :data:`MAX_ENTRIES_PER_OPERATOR` (= 100)
to keep the CMap parser-friendly (PDFBOX-4302).
"""

from __future__ import annotations

import io
import math


def _hex_short(value: int) -> str:
    """Format *value* as 4 hex digits, uppercase. Mirrors ``Hex.getChars(short)``."""
    return format(value & 0xFFFF, "04X")


def _hex_utf16be(text: str) -> str:
    """Encode *text* as UTF-16BE hex digits, uppercase. Mirrors ``Hex.getCharsUTF16BE(String)``."""
    return text.encode("utf-16-be").hex().upper()


class ToUnicodeWriter:
    """Builds a ToUnicode CMap stream incrementally.

    Mirrors upstream Java line 36-228.
    """

    #: Maximum ``begincodespacerange`` entries per operator. Tested for
    #: corner case PDFBOX-4302 (Java line 44).
    MAX_ENTRIES_PER_OPERATOR: int = 100

    def __init__(self) -> None:
        # Upstream uses a ``TreeMap<Integer, String>`` — Python's dict is
        # insertion-ordered, but to match upstream's sort-by-key semantics
        # we explicitly sort at write time.
        self._cid_to_unicode: dict[int, str] = {}
        self._w_mode: int = 0

    def set_w_mode(self, w_mode: int) -> None:
        """Set the writing mode (0 = horizontal, 1 = vertical).

        Mirrors upstream ``setWMode`` (Java line 59-62).
        """
        self._w_mode = w_mode

    @staticmethod
    def write_line(buf: io.StringIO, text: str) -> None:
        """Mirror upstream ``writeLine(BufferedWriter, String)`` (Java
        line 178-182): write *text* followed by ``'\\n'`` to *buf*."""
        buf.write(text)
        buf.write("\n")

    def add(self, cid: int, text: str) -> None:
        """Register a ``cid -> text`` mapping.

        Mirrors upstream ``add(int, String)`` (Java line 70-83). Raises
        :class:`ValueError` (upstream throws ``IllegalArgumentException``)
        if *cid* is outside ``[0, 0xFFFF]`` or *text* is empty/None.
        """
        if cid < 0 or cid > 0xFFFF:
            raise ValueError("CID is not valid")
        if not text:
            raise ValueError("Text is null or empty")
        self._cid_to_unicode[cid] = text

    def write_to(self, out: io.BufferedIOBase | io.RawIOBase) -> None:
        """Write the ASCII CMap to *out*.

        Mirrors upstream ``writeTo(OutputStream)`` (Java line 91-176).
        Upstream wraps the stream in a ``BufferedWriter`` with US_ASCII;
        Python accepts any byte-oriented stream and encodes each chunk
        on the fly.
        """
        buf = io.StringIO()

        def write_line(text: str) -> None:
            self.write_line(buf, text)

        write_line("/CIDInit /ProcSet findresource begin")
        write_line("12 dict begin\n")

        write_line("begincmap")
        write_line("/CIDSystemInfo")
        write_line("<< /Registry (Adobe)")
        write_line("/Ordering (UCS)")
        write_line("/Supplement 0")
        write_line(">> def\n")

        write_line("/CMapName /Adobe-Identity-UCS def")
        write_line("/CMapType 2 def\n")  # 2 = ToUnicode

        if self._w_mode != 0:
            write_line(f"/WMode /{self._w_mode} def")

        # ToUnicode always uses 16-bit CIDs (Java line 113-116).
        write_line("1 begincodespacerange")
        write_line("<0000> <FFFF>")
        write_line("endcodespacerange\n")

        # CID -> Unicode mappings, collapsed into ranges where allowed.
        src_from: list[int] = []
        src_to: list[int] = []
        dst_string: list[str] = []

        prev: tuple[int, str] | None = None
        # Walk in sorted-by-CID order to match upstream TreeMap iteration.
        for cid in sorted(self._cid_to_unicode):
            text = self._cid_to_unicode[cid]
            current: tuple[int, str] = (cid, text)
            if self.allow_cid_to_unicode_range(prev, current):
                # extend current range
                src_to[-1] = cid
            else:
                # begin new range
                src_from.append(cid)
                src_to.append(cid)
                dst_string.append(text)
            prev = current

        # Emit batched ``beginbfrange`` operators (Java line 143-167).
        batch_count = int(
            math.ceil(len(src_from) / float(self.MAX_ENTRIES_PER_OPERATOR))
        )
        for batch in range(batch_count):
            if batch == batch_count - 1:
                count = len(src_from) - self.MAX_ENTRIES_PER_OPERATOR * batch
            else:
                count = self.MAX_ENTRIES_PER_OPERATOR
            buf.write(f"{count} beginbfrange\n")
            for j in range(count):
                index = batch * self.MAX_ENTRIES_PER_OPERATOR + j
                buf.write("<")
                buf.write(_hex_short(src_from[index]))
                buf.write("> ")
                buf.write("<")
                buf.write(_hex_short(src_to[index]))
                buf.write("> ")
                buf.write("<")
                buf.write(_hex_utf16be(dst_string[index]))
                buf.write(">\n")
            write_line("endbfrange\n")

        # Footer (Java line 169-173).
        write_line("endcmap")
        write_line("CMapName currentdict /CMap defineresource pop")
        write_line("end")
        write_line("end")

        # Upstream flushes the writer (Java line 175). We flush our buffer
        # and emit US-ASCII bytes to the caller-supplied stream.
        out.write(buf.getvalue().encode("ascii"))

    @staticmethod
    def allow_cid_to_unicode_range(
        prev: tuple[int, str] | None,
        next_entry: tuple[int, str] | None,
    ) -> bool:
        """Return ``True`` if the two ``(cid, text)`` entries can be a range.

        Mirrors upstream ``allowCIDToUnicodeRange`` (Java line 186-195).
        """
        if prev is None or next_entry is None:
            return False
        return ToUnicodeWriter.allow_code_range(
            prev[0], next_entry[0]
        ) and ToUnicodeWriter.allow_destination_range(prev[1], next_entry[1])

    @staticmethod
    def allow_code_range(prev: int, next_value: int) -> bool:
        """Return ``True`` iff *next* immediately follows *prev* in low byte.

        Mirrors upstream ``allowCodeRange`` (Java line 198-210).
        """
        if (prev + 1) != next_value:
            return False
        prev_h = (prev >> 8) & 0xFF
        prev_l = prev & 0xFF
        next_h = (next_value >> 8) & 0xFF
        next_l = next_value & 0xFF
        return prev_h == next_h and prev_l < next_l

    @staticmethod
    def allow_destination_range(prev: str, next_text: str) -> bool:
        """Return ``True`` iff destination strings can be merged into a range.

        Mirrors upstream ``allowDestinationRange`` (Java line 214-227).
        """
        if not prev or not next_text:
            return False
        prev_code = ord(prev[0]) if len(prev) >= 1 else 0
        next_code = ord(next_text[0]) if len(next_text) >= 1 else 0
        # Mirror upstream: must be sequential AND the previous string
        # must be a single code point (no surrogate pair).
        return (
            ToUnicodeWriter.allow_code_range(prev_code, next_code)
            and len(prev) == 1
        )


__all__ = ["ToUnicodeWriter"]
