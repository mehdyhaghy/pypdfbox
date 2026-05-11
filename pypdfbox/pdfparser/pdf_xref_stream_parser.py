from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos.cos_array import COSArray
from pypdfbox.cos.cos_integer import COSInteger
from pypdfbox.cos.cos_name import COSName
from pypdfbox.cos.cos_object_key import COSObjectKey

from .base_parser import BaseParser
from .object_numbers import ObjectNumbers
from .parse_error import PDFParseError

if TYPE_CHECKING:
    from pypdfbox.cos.cos_document import COSDocument
    from pypdfbox.cos.cos_stream import COSStream

    from .xref_trailer_resolver import XrefTrailerResolver


class PDFXrefStreamParser(BaseParser):
    """Parser for PDF 1.5+ cross-reference streams.

    Mirrors upstream
    ``org.apache.pdfbox.pdfparser.PDFXrefStreamParser``. Reads the
    ``/W`` field-widths and ``/Index`` object-number ranges from the
    stream dictionary, then walks the raw stream bytes producing
    per-object byte offsets (for normal entries) or
    object-stream-and-index pairs (for compressed entries) and feeds
    them to a :class:`XrefTrailerResolver`.
    """

    def __init__(self, stream: COSStream, document: COSDocument) -> None:
        super().__init__(stream.create_view())
        self._document = document
        self._w: list[int] = [0, 0, 0]
        self._object_numbers: ObjectNumbers | None = None
        try:
            self._init_parser_values(stream)
        except OSError:
            self.close()
            raise

    # ------------------------------------------------------------------
    # Initialisation — read /W and /Index from the stream dictionary
    # ------------------------------------------------------------------

    def _init_parser_values(self, stream: COSStream) -> None:
        w_array = stream.get_cos_array(COSName.W)
        if w_array is None:
            raise PDFParseError("/W array is missing in Xref stream")
        if len(w_array) != 3:
            raise PDFParseError(
                f"Wrong number of values for /W array in XRef: {list(self._w)}"
            )
        for i in range(3):
            self._w[i] = w_array.get_int(i, 0)
        if any(v < 0 for v in self._w):
            raise PDFParseError(f"Incorrect /W array in XRef: {list(self._w)}")
        # PDFBOX-6037: refuse pathological widths.
        if sum(self._w) > 20:
            raise PDFParseError(f"Incorrect /W array in XRef: {list(self._w)}")

        index_array = stream.get_cos_array(COSName.INDEX)
        if index_array is None:
            index_array = COSArray()
            index_array.add(COSInteger.ZERO)
            index_array.add(COSInteger.get(stream.get_int(COSName.SIZE, 0)))
        if len(index_array) == 0 or len(index_array) % 2 == 1:
            raise PDFParseError(
                f"Wrong number of values for /Index array in XRef: {list(self._w)}"
            )
        self._object_numbers = ObjectNumbers(index_array)

    # ------------------------------------------------------------------
    # Main parse loop
    # ------------------------------------------------------------------

    def parse(self, resolver: XrefTrailerResolver) -> None:
        """Walk the stream bytes and feed entries into ``resolver``.

        Mirrors upstream ``PDFXrefStreamParser.parse`` (Java line 127).
        """
        assert self._object_numbers is not None
        curr_line = bytearray(self._w[0] + self._w[1] + self._w[2])
        while not self.is_eof() and self._object_numbers.has_next():
            self._read_next_value(curr_line)
            obj_id = self._object_numbers.next_value()
            # Type defaults to 1 (in-use, uncompressed) when /W[0] == 0,
            # per the PDF spec.
            type_ = 1 if self._w[0] == 0 else int(self._parse_value(curr_line, 0, self._w[0]))
            if type_ == 0:
                # Free entry — skipped here; the resolver tracks free
                # entries separately.
                continue
            offset = self._parse_value(curr_line, self._w[0], self._w[1])
            third_value = int(
                self._parse_value(curr_line, self._w[0] + self._w[1], self._w[2])
            )
            if type_ == 1:
                resolver.set_x_ref(COSObjectKey(obj_id, third_value), offset)
            else:
                # Compressed entry: ``offset`` is the object-stream
                # object number, ``third_value`` is the index within it.
                # Encode the object-stream membership using a negative
                # offset — matches the convention COSDocument uses for
                # its xref-table values (negative = inside object stream).
                resolver.set_x_ref(
                    COSObjectKey(obj_id, 0, third_value), -offset
                )
        self._close()

    # ------------------------------------------------------------------
    # Helpers — match upstream private method shapes
    # ------------------------------------------------------------------

    def read_next_value(self, value: bytearray) -> None:
        """Read ``len(value)`` bytes into ``value``.

        Mirrors upstream ``readNextValue`` (Java line 162, private).
        Promoted to public so the upstream method surface is preserved.
        """
        remaining = len(value)
        while True:
            amount = self._src.read_into(value, len(value) - remaining, remaining)
            if amount <= 0:
                break
            remaining -= amount
            if remaining <= 0:
                break

    _read_next_value = read_next_value

    @staticmethod
    def parse_value(data: bytearray, start: int, length: int) -> int:
        """Parse a big-endian integer of ``length`` bytes from ``data``.

        Mirrors upstream ``parseValue`` (Java line 172, private).
        Promoted to public for parity.
        """
        value = 0
        for i in range(length):
            value += (data[i + start] & 0xFF) << ((length - i - 1) * 8)
        return value

    _parse_value = parse_value

    def close(self) -> None:
        """Release the underlying source and the index iterator.

        Mirrors upstream ``close`` (Java line 111, private). Promoted to
        public to match the surface.
        """
        if self._src is not None:
            self._src.close()
        self._document = None  # type: ignore[assignment]
        self._object_numbers = None

    _close = close

    def init_parser_values(self, stream: COSStream) -> None:
        """Read /W and /Index from the stream dictionary.

        Mirrors upstream ``initParserValues`` (Java line 68, private).
        Promoted to public for parity.
        """
        self._init_parser_values(stream)
