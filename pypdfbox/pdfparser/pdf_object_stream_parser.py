from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos.cos_name import COSName
from pypdfbox.cos.cos_object_key import COSObjectKey

from .base_parser import BaseParser
from .parse_error import PDFParseError

if TYPE_CHECKING:
    from pypdfbox.cos.cos_base import COSBase
    from pypdfbox.cos.cos_document import COSDocument
    from pypdfbox.cos.cos_stream import COSStream


class PDFObjectStreamParser(BaseParser):
    """Parser for PDF 1.5+ object streams.

    Mirrors upstream
    ``org.apache.pdfbox.pdfparser.PDFObjectStreamParser``. Reads the
    ``/N`` (number of objects) and ``/First`` (offset of the first
    object) header fields from the stream dictionary, then walks the
    list of ``(object_number, offset)`` pairs at the top of the stream.
    """

    def __init__(self, stream: COSStream, document: COSDocument) -> None:
        super().__init__(stream.create_view())
        self._document = document
        n = stream.get_int(COSName.N)
        if n == -1:
            raise PDFParseError("/N entry missing in object stream")
        if n < 0:
            raise PDFParseError(f"Illegal /N entry in object stream: {n}")
        self._number_of_objects: int = n
        first = stream.get_int(COSName.FIRST)
        if first == -1:
            raise PDFParseError("/First entry missing in object stream")
        if first < 0:
            raise PDFParseError(f"Illegal /First entry in object stream: {first}")
        self._first_object: int = first

    # ------------------------------------------------------------------
    # Parse a single object
    # ------------------------------------------------------------------

    def parse_object(self, object_number: int) -> COSBase | None:
        """Parse the object with the given number from the stream.

        Mirrors upstream ``PDFObjectStreamParser.parseObject`` (Java line
        83). Returns ``None`` if the object is not present.
        """
        stream_object: COSBase | None = None
        try:
            offsets = self._private_read_object_numbers()
            offset = offsets.get(object_number)
            if offset is not None:
                current_position = self._src.get_position()
                if self._first_object > 0 and current_position < self._first_object:
                    self._src.skip(self._first_object - int(current_position))
                self._src.skip(offset)
                stream_object = self.parse_dir_object()
                if stream_object is not None:
                    stream_object.set_direct(False)
        finally:
            self._src.close()
            self._document = None  # type: ignore[assignment]
        return stream_object

    # ------------------------------------------------------------------
    # Parse all objects in the stream
    # ------------------------------------------------------------------

    def parse_all_objects(self) -> dict[COSObjectKey, COSBase | None]:
        """Parse every compressed object in the stream.

        Mirrors upstream ``PDFObjectStreamParser.parseAllObjects`` (Java
        line 120). Returns a mapping ``COSObjectKey → COSBase``.
        """
        all_objects: dict[COSObjectKey, COSBase | None] = {}
        try:
            object_numbers = self._private_read_object_offsets()
            # Count unique object numbers — see PDFBOX-4927.
            number_of_obj_numbers = len(set(object_numbers.values()))
            index_needed = len(object_numbers) > number_of_obj_numbers
            current_position = self._src.get_position()
            if self._first_object > 0 and current_position < self._first_object:
                self._src.skip(self._first_object - int(current_position))
            index = 0
            for offset_key, object_number in object_numbers.items():
                object_key = self.get_object_key(object_number, 0)
                if (
                    index_needed
                    and object_key.get_stream_index() > -1
                    and object_key.get_stream_index() != index
                ):
                    index += 1
                    continue
                final_position = self._first_object + offset_key
                current_position = self._src.get_position()
                if final_position > 0 and current_position < final_position:
                    self._src.skip(final_position - int(current_position))
                stream_object = self.parse_dir_object()
                if stream_object is not None:
                    stream_object.set_direct(False)
                all_objects[object_key] = stream_object
                index += 1
        finally:
            self._src.close()
            self._document = None  # type: ignore[assignment]
        return all_objects

    # ------------------------------------------------------------------
    # Header table — public + private variants matching upstream
    # ------------------------------------------------------------------

    def read_object_numbers(self) -> dict[int, int]:
        """Return ``{object_number: offset_within_stream}``.

        Mirrors upstream ``PDFObjectStreamParser.readObjectNumbers``
        (Java line 220). Closes the underlying source on exit.
        """
        try:
            return self._private_read_object_numbers()
        finally:
            self._src.close()
            self._document = None  # type: ignore[assignment]

    # ------------------------------------------------------------------
    # Helpers — match upstream private method names
    # ------------------------------------------------------------------

    def private_read_object_numbers(self) -> dict[int, int]:
        """Public alias for :meth:`_private_read_object_numbers`
        matching the upstream method name."""
        return self._private_read_object_numbers()

    def _private_read_object_numbers(self) -> dict[int, int]:
        """Mirrors upstream ``privateReadObjectNumbers`` (Java line 174,
        private)."""
        result: dict[int, int] = {}
        first_object_position = self._src.get_position() + self._first_object - 1
        for _ in range(self._number_of_objects):
            if self._src.get_position() >= first_object_position:
                break
            object_number = self.read_object_number()
            offset = int(self.read_long())
            result[object_number] = offset
        return result

    def private_read_object_offsets(self) -> dict[int, int]:
        """Public alias for :meth:`_private_read_object_offsets`
        matching the upstream method name."""
        return self._private_read_object_offsets()

    def _private_read_object_offsets(self) -> dict[int, int]:
        """Mirrors upstream ``privateReadObjectOffsets`` (Java line 193,
        private). Returns ``{offset: object_number}`` keyed by offset so
        callers can walk objects in stream order even when the dict
        spec violates the ``/First`` ordering convention (PDFBOX-4927).
        """
        result: dict[int, int] = {}
        first_object_position = self._src.get_position() + self._first_object - 1
        for _ in range(self._number_of_objects):
            if self._src.get_position() >= first_object_position:
                break
            object_number = self.read_object_number()
            offset = int(self.read_long())
            result[offset] = object_number
        return dict(sorted(result.items()))

    # ------------------------------------------------------------------
    # COSObjectKey helper — match upstream's ``getObjectKey`` which lives
    # on COSParser. If not available, fall back to a plain construction.
    # ------------------------------------------------------------------

    def get_object_key(self, number: int, generation: int) -> COSObjectKey:
        helper = getattr(super(), "get_object_key", None)
        if callable(helper):
            return helper(number, generation)
        return COSObjectKey(number, generation)
