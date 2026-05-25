from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos.cos_array import COSArray
from pypdfbox.cos.cos_integer import COSInteger
from pypdfbox.cos.cos_name import COSName

from .xref.free_x_reference import FreeXReference

if TYPE_CHECKING:
    from pypdfbox.cos.cos_dictionary import COSDictionary
    from pypdfbox.cos.cos_document import COSDocument
    from pypdfbox.cos.cos_stream import COSStream

    from .xref.x_reference_entry import XReferenceEntry


class PDFXRefStream:
    """Builder for a PDF 1.5+ cross-reference stream.

    Mirrors upstream ``org.apache.pdfbox.pdfparser.PDFXRefStream``.
    Callers add :class:`XReferenceEntry` rows via :meth:`add_entry`,
    then ask for the finished ``COSStream`` via :meth:`get_stream` —
    the builder computes the optimal ``/W`` widths, packs the entries
    into a Flate-encoded byte sequence, and sets all required keys
    (``/Type``, ``/Size``, ``/Index``, ``/W``).
    """

    def __init__(self, cos_document: COSDocument) -> None:
        self._stream_data: list[XReferenceEntry] = []
        self._object_numbers: set[int] = set()
        self._stream: COSStream = cos_document.create_cos_stream()
        self._size: int = -1

    # ------------------------------------------------------------------
    # Trailer / metadata
    # ------------------------------------------------------------------

    def add_trailer_info(self, trailer_dict: COSDictionary) -> None:
        """Copy trailer entries (``/Info``, ``/Root``, ``/Encrypt``,
        ``/ID``, ``/Prev``) from ``trailer_dict`` into the stream.

        Mirrors upstream ``addTrailerInfo`` (Java line 123).
        """
        for key in (COSName.INFO, COSName.ROOT, COSName.ENCRYPT, COSName.ID, COSName.PREV):
            if trailer_dict.contains_key(key):
                self._stream.set_item(key, trailer_dict.get_item(key))

    def add_entry(self, entry: XReferenceEntry) -> None:
        """Add an xref entry. Duplicates by object number are dropped.

        Mirrors upstream ``addEntry`` (Java line 140).
        """
        num = entry.get_referenced_key().get_number()
        if num in self._object_numbers:
            return
        self._object_numbers.add(num)
        self._stream_data.append(entry)

    def set_size(self, stream_size: int) -> None:
        """Set the stream's logical ``/Size`` (largest object number + 1).

        Mirrors upstream ``setSize`` (Java line 182).
        """
        self._size = stream_size

    # ------------------------------------------------------------------
    # Finalization
    # ------------------------------------------------------------------

    def get_stream(self) -> COSStream:
        """Build the finished xref ``COSStream``.

        Mirrors upstream ``getStream`` (Java line 67). Sets ``/Type``,
        ``/Size``, ``/Index``, ``/W``, and writes the Flate-encoded
        column data into the stream body.
        """
        self._stream.set_item(COSName.TYPE, COSName.XREF)
        if self._size == -1:
            raise ValueError("size is not set in xrefstream")
        self._stream.set_long(COSName.SIZE, self._size)

        index_entry = self._get_index_entry()
        index_as_array = COSArray()
        for value in index_entry:
            index_as_array.add(COSInteger.get(value))
        self._stream.set_item(COSName.INDEX, index_as_array)

        w_entry = self._get_w_entry()
        w_as_array = COSArray()
        for value in w_entry:
            w_as_array.add(COSInteger.get(value))
        self._stream.set_item(COSName.W, w_as_array)

        out = self._stream.create_output_stream(COSName.FLATE_DECODE)
        try:
            self._write_stream_data(out, w_entry)
            out.flush()
        finally:
            out.close()

        # Force certain entries to remain indirect / direct per spec.
        for cos_name in list(self._stream.key_set()):
            if cos_name in (COSName.ROOT, COSName.INFO, COSName.PREV):
                continue
            if cos_name == COSName.ENCRYPT:
                continue
            dictionary_object = self._stream.get_dictionary_object(cos_name)
            if dictionary_object is not None:
                dictionary_object.set_direct(True)
        return self._stream

    # ------------------------------------------------------------------
    # Helpers — private upstream methods promoted to underscore-prefixed.
    # ------------------------------------------------------------------

    def get_w_entry(self) -> list[int]:
        """Public alias for :meth:`_get_w_entry` matching upstream's
        ``getWEntry`` method name."""
        return self._get_w_entry()

    def _get_w_entry(self) -> list[int]:
        """Return the ``/W`` widths (in bytes) — one per column.

        Mirrors upstream ``getWEntry`` (Java line 155). Each width is
        the minimum number of bytes needed to represent the largest
        value in that column.
        """
        w_max = [0, 0, 0]
        for entry in self._stream_data:
            w_max[0] = max(w_max[0], entry.get_first_column_value())
            w_max[1] = max(w_max[1], entry.get_second_column_value())
            w_max[2] = max(w_max[2], entry.get_third_column_value())
        widths = [0, 0, 0]
        for i in range(3):
            v = w_max[i]
            while v > 0:
                widths[i] += 1
                v >>= 8
        return widths

    def get_index_entry(self) -> list[int]:
        """Public alias for :meth:`_get_index_entry` matching upstream's
        ``getIndexEntry`` method name."""
        return self._get_index_entry()

    def _get_index_entry(self) -> list[int]:
        """Return the ``/Index`` array values — alternating
        ``(first, length)`` pairs covering all referenced object
        numbers (always including 0).

        Mirrors upstream ``getIndexEntry`` (Java line 187).
        """
        linked: list[int] = []
        first: int | None = None
        length: int | None = None
        obj_numbers: set[int] = {0}
        obj_numbers.update(self._object_numbers)
        for num in sorted(obj_numbers):
            if first is None:
                first = num
                length = 1
                continue
            assert length is not None
            if first + length == num:
                length += 1
            elif first + length < num:  # pragma: no branch
                # No else: sorted unique set guarantees first+length <= num.
                linked.append(first)
                linked.append(length)
                first = num
                length = 1
        if first is not None and length is not None:  # pragma: no branch
            # obj_numbers always seeded with {0}; first is non-None at end.
            linked.append(first)
            linked.append(length)
        return linked

    @staticmethod
    def write_number(out: object, number: int, n_bytes: int) -> None:
        """Public alias for :meth:`_write_number` matching upstream's
        ``writeNumber`` method name."""
        PDFXRefStream._write_number(out, number, n_bytes)

    @staticmethod
    def _write_number(out: object, number: int, n_bytes: int) -> None:
        """Big-endian-write ``number`` as ``n_bytes`` bytes.

        Mirrors upstream ``writeNumber`` (Java line 221, private).
        """
        buffer = bytearray(n_bytes)
        v = number
        for i in range(n_bytes):
            buffer[i] = v & 0xFF
            v >>= 8
        # Reverse to big-endian and write as a single bytes blob —
        # Python's stream ``write`` expects bytes-like, not single ints.
        buffer.reverse()
        out.write(bytes(buffer))  # type: ignore[attr-defined]

    def write_stream_data(self, out: object, w: list[int]) -> None:
        """Public alias for :meth:`_write_stream_data` matching upstream's
        ``writeStreamData`` method name."""
        self._write_stream_data(out, w)

    def _write_stream_data(self, out: object, w: list[int]) -> None:
        """Write the ``NULL_ENTRY`` row plus each :class:`XReferenceEntry`
        in sorted order.

        Mirrors upstream ``writeStreamData`` (Java line 236, private).
        """
        self._stream_data.sort()
        null_entry = FreeXReference.NULL_ENTRY
        self._write_number(out, null_entry.get_first_column_value(), w[0])
        self._write_number(out, null_entry.get_second_column_value(), w[1])
        self._write_number(out, null_entry.get_third_column_value(), w[2])
        for entry in self._stream_data:
            self._write_number(out, entry.get_first_column_value(), w[0])
            self._write_number(out, entry.get_second_column_value(), w[1])
            self._write_number(out, entry.get_third_column_value(), w[2])
