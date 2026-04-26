from __future__ import annotations

import io
from collections.abc import Iterable, Sequence
from typing import TYPE_CHECKING, BinaryIO

from pypdfbox.cos import COSArray, COSBase, COSDocument, COSName, COSStream
from pypdfbox.filter import FilterFactory

if TYPE_CHECKING:
    from pypdfbox.pdmodel.pd_document import PDDocument


_FILTER: COSName = COSName.FILTER  # type: ignore[attr-defined]
_LENGTH: COSName = COSName.LENGTH  # type: ignore[attr-defined]
_DL: COSName = COSName.get_pdf_name("DL")


class PDStream:
    """
    PDF stream wrapper. Mirrors
    ``org.apache.pdfbox.pdmodel.common.PDStream``.

    A PDStream is a thin typed handle over a ``COSStream`` (the dictionary
    + binary body). It exposes filter-aware input/output streams and
    convenience accessors for ``/Filter``, ``/Length``, and ``/DL``.

    The upstream class has eight overloaded constructors. Python's single
    ``__init__`` collapses them via type-dispatch on the first positional
    argument:

    - ``PDStream()``                       — wrap a fresh empty COSStream.
    - ``PDStream(cos_stream)``             — wrap an existing COSStream.
    - ``PDStream(document)``               — create empty stream owned by
      the PDDocument / COSDocument.
    - ``PDStream(document, input)``        — embed bytes/stream into a new
      stream owned by the document. Optional ``filters`` (single ``COSName``
      or ``COSArray`` of names) records the filter chain on the new
      ``/Filter`` entry.
    """

    def __init__(
        self,
        document_or_stream: PDDocument | COSDocument | COSStream | None = None,
        input_data: bytes | bytearray | memoryview | BinaryIO | None = None,
        filters: COSName | COSArray | None = None,
    ) -> None:
        # Local import to avoid cycle (PDDocument -> PDPage -> PDResources -> ...).
        from pypdfbox.pdmodel.pd_document import PDDocument  # noqa: PLC0415

        if document_or_stream is None:
            self._stream: COSStream = COSStream()
        elif isinstance(document_or_stream, COSStream):
            if input_data is not None:
                raise TypeError(
                    "PDStream(cos_stream, input_data) is not a valid overload — "
                    "pass a document when supplying input bytes"
                )
            self._stream = document_or_stream
        elif isinstance(document_or_stream, (PDDocument, COSDocument)):
            self._stream = COSStream()
            if input_data is not None:
                self._embed(input_data, filters)
        else:
            raise TypeError(
                f"PDStream expected None, COSStream, COSDocument, or PDDocument; "
                f"got {type(document_or_stream).__name__}"
            )

    # ---------- internal helpers ----------

    def _embed(
        self,
        input_data: bytes | bytearray | memoryview | BinaryIO,
        filters: COSName | COSArray | None,
    ) -> None:
        """Read ``input_data`` and write the (raw) bytes into the wrapped
        ``COSStream``. The ``filters`` argument, if given, populates the
        stream's ``/Filter`` entry — but no encoding is performed: the
        bytes you pass in are stored as-is and are assumed to already be
        in the encoded form indicated by ``filters``.

        Mirrors upstream's ``PDStream(PDDocument, InputStream, COSBase)``
        which calls ``stream.createOutputStream(filters)``; PDFBox 3 does
        encode on write. We match the *recorded filter list* but stash
        the raw bytes (encoding-on-write is filter-cluster #2 territory)."""
        if isinstance(input_data, (bytes, bytearray, memoryview)):
            data = bytes(input_data)
        else:
            data = input_data.read()
            if hasattr(input_data, "close"):
                try:
                    input_data.close()
                except Exception:  # noqa: BLE001 — match upstream's "close quietly"
                    pass
        self._stream.set_raw_data(data)
        if filters is not None:
            self._stream.set_item(_FILTER, filters)

    # ---------- COS surface ----------

    def get_cos_object(self) -> COSStream:
        return self._stream

    # ---------- output streams ----------

    def create_output_stream(self, filter: COSName | None = None) -> BinaryIO:  # noqa: A002
        """Writable stream — on close, its contents become the body. If
        ``filter`` is supplied, it's recorded on ``/Filter`` (encoding
        itself is filter-cluster #2 territory; today ``COSStream`` raises
        ``NotImplementedError`` if a filter is passed through to it)."""
        return self._stream.create_output_stream(filter)

    # ---------- input streams ----------

    def create_input_stream(
        self,
        stop_filters: Sequence[str | COSName] | None = None,
    ) -> BinaryIO:
        """Decoded read stream.

        - With no ``/Filter`` set → returns the raw bytes.
        - With filters set → applies each registered filter in order. If
          ``stop_filters`` is provided, decoding *stops at* (i.e. doesn't
          run) the first filter whose name appears in ``stop_filters`` —
          the remaining filters' encoded bytes are returned as-is. This
          mirrors upstream ``createInputStream(List<String>)`` and is used
          by image XObjects to short-circuit DCT/JBIG2 decoding.

        Returns a ``BytesIO`` over the decoded payload. Raises ``KeyError``
        when the chain references a filter not registered in
        ``FilterFactory``."""
        filters = self.get_filters()
        if not filters:
            return self._stream.create_raw_input_stream()

        stop_set: set[str] = set()
        if stop_filters is not None:
            for s in stop_filters:
                stop_set.add(s.name if isinstance(s, COSName) else s)

        encoded = self._stream.get_raw_data()
        # Apply filters in order, halting at the first stop filter.
        for index, filter_name in enumerate(filters):
            if filter_name.name in stop_set:
                break
            f = FilterFactory.get(filter_name)
            src = io.BytesIO(encoded)
            dst = io.BytesIO()
            f.decode(src, dst, self._stream, index)
            encoded = dst.getvalue()
        return io.BytesIO(encoded)

    def create_raw_input_stream(self) -> BinaryIO:
        """Raw (still-encoded) bytes."""
        return self._stream.create_raw_input_stream()

    # ---------- length ----------

    def get_length(self) -> int:
        """``/Length`` — encoded body length. Returns 0 when absent."""
        return self._stream.get_int(_LENGTH, 0)

    def get_decoded_stream_length(self) -> int:
        """``/DL`` — decoded body length hint (may be absent → -1)."""
        return self._stream.get_int(_DL, -1)

    def set_decoded_stream_length(self, length: int) -> None:
        self._stream.set_int(_DL, int(length))

    # ---------- filters ----------

    def get_filters(self) -> list[COSName]:
        """``/Filter`` chain as a list. Empty when absent. Mirrors
        upstream ``getFilters() : List<COSName>``."""
        f = self._stream.get_dictionary_object(_FILTER)
        if f is None:
            return []
        if isinstance(f, COSName):
            return [f]
        if isinstance(f, COSArray):
            out: list[COSName] = []
            for entry in f:
                if isinstance(entry, COSName):
                    out.append(entry)
                else:
                    raise TypeError(
                        f"non-name entry in /Filter array: {type(entry).__name__}"
                    )
            return out
        raise TypeError(f"unexpected /Filter type: {type(f).__name__}")

    def set_filters(
        self,
        filters: COSName | str | Iterable[COSName | str] | None,
    ) -> None:
        """Replace ``/Filter``. Accepts:

        - ``None``         → remove the entry.
        - single ``COSName`` / ``str`` → record as a one-name array
          (matches upstream ``setFilters(List)`` which always wraps).
        - iterable of names → record as an array.
        """
        if filters is None:
            self._stream.remove_item(_FILTER)
            return
        if isinstance(filters, (COSName, str)):
            names = [_to_name(filters)]
        else:
            names = [_to_name(n) for n in filters]
        arr = COSArray(names)
        self._stream.set_item(_FILTER, arr)

    # ---------- bytes convenience ----------

    def to_byte_array(self) -> bytes:
        """Return the *decoded* body as a ``bytes``. Mirrors upstream
        ``toByteArray()``."""
        with self.create_input_stream() as src:
            return src.read()


def _to_name(value: COSName | str) -> COSName:
    if isinstance(value, COSName):
        return value
    return COSName.get_pdf_name(value)
