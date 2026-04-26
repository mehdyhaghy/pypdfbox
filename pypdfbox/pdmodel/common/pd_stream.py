from __future__ import annotations

from collections.abc import Iterable, Sequence
from contextlib import suppress
from typing import TYPE_CHECKING, BinaryIO

from pypdfbox.cos import COSArray, COSDictionary, COSDocument, COSName, COSStream

if TYPE_CHECKING:
    from pypdfbox.pdmodel.pd_document import PDDocument


_FILTER: COSName = COSName.FILTER  # type: ignore[attr-defined]
_LENGTH: COSName = COSName.LENGTH  # type: ignore[attr-defined]
_METADATA: COSName = COSName.METADATA  # type: ignore[attr-defined]
_DL: COSName = COSName.get_pdf_name("DL")
_DECODE_PARMS: COSName = COSName.get_pdf_name("DecodeParms")


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
            if input_data is not None:
                self._embed(input_data, filters)
        elif isinstance(document_or_stream, COSStream):
            if input_data is not None:
                raise TypeError(
                    "PDStream(cos_stream, input_data) is not a valid overload — "
                    "pass a document when supplying input bytes"
                )
            self._stream = document_or_stream
        elif isinstance(document_or_stream, (PDDocument, COSDocument)):
            cos_doc = (
                document_or_stream.get_document()
                if isinstance(document_or_stream, PDDocument)
                else document_or_stream
            )
            self._stream = COSStream(cos_doc.scratch_file)
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
        """Read ``input_data`` and write the bytes into the wrapped
        ``COSStream``. The ``filters`` argument, if given, populates
        ``/Filter`` and the bytes are stored as-is (already-encoded form).

        Mirrors upstream's ``PDStream(PDDocument, InputStream, COSBase)``
        which calls ``stream.createOutputStream(filters)``; we keep the
        same shape but the caller is expected to pass already-encoded
        bytes when ``filters`` is set (encode-on-embed would force callers
        to pass the *decoded* form, which breaks every existing call site
        that hands us pre-compressed bytes)."""
        if isinstance(input_data, (bytes, bytearray, memoryview)):
            data = bytes(input_data)
        else:
            data = input_data.read()
            if hasattr(input_data, "close"):
                with suppress(Exception):
                    input_data.close()
        self._stream.set_raw_data(data)
        if filters is not None:
            self._stream.set_item(_FILTER, filters)

    # ---------- COS surface ----------

    def get_cos_object(self) -> COSStream:
        return self._stream

    # ---------- output streams ----------

    def create_output_stream(
        self,
        filters: COSName | str | Sequence[COSName | str] | None = None,
    ) -> BinaryIO:
        """Writable stream — on ``close()`` its contents become the body.

        With ``filters`` supplied, the bytes you write are *encoded*
        through the chain on close (and ``/Filter`` is updated). Without
        filters, bytes are stored verbatim and any existing ``/Filter``
        entry is left untouched."""
        return self._stream.create_output_stream(filters)

    # ---------- input streams ----------

    def create_input_stream(
        self,
        stop_filters: Sequence[str | COSName] | None = None,
    ) -> BinaryIO:
        """Decoded read stream — delegates to
        :meth:`COSStream.create_input_stream`.

        - With no ``/Filter`` set → returns the raw bytes.
        - With filters set → applies each registered filter in order. If
          ``stop_filters`` is provided, decoding *stops at* (i.e. doesn't
          run) the first filter whose name appears in ``stop_filters`` —
          the remaining filters' encoded bytes are returned as-is. This
          mirrors upstream ``createInputStream(List<String>)`` and is used
          by image XObjects to short-circuit DCT/JBIG2 decoding.

        For an empty stream (no body set), returns an empty ``BytesIO``
        rather than raising — matches the natural "no data" case. (This
        diverges slightly from ``COSStream.create_input_stream``, which
        raises ``OSError``: callers of ``PDStream`` are typed handles
        that often legitimately wrap a fresh-and-empty COSStream.)"""
        if not self._stream.has_data():
            import io as _io  # noqa: PLC0415 — local to avoid leaking name

            return _io.BytesIO(b"")
        return self._stream.create_input_stream(stop_filters)

    def create_raw_input_stream(self) -> BinaryIO:
        """Raw (still-encoded) bytes."""
        return self._stream.create_raw_input_stream()

    # ---------- length ----------

    def get_length(self) -> int | None:
        """``/Length`` — encoded body length. Returns the dictionary
        value when present (parser-populated), else falls back to the
        live raw-byte length, else ``None`` for an entirely empty
        stream. Mirrors upstream ``getLength()`` whose dictionary
        access can yield a missing entry."""
        length = self._stream.get_int(_LENGTH, -1)
        if length >= 0:
            return length
        # Fall back to the live buffer; 0 still counts as a real length.
        if self._stream.has_data():
            return self._stream.get_length()
        # No /Length entry and no body — match upstream's "missing".
        if not self._stream.contains_key(_LENGTH):
            return None
        return 0

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

    # ---------- decode parameters ----------

    def get_decode_parms(self) -> list[COSDictionary] | None:
        """``/DecodeParms`` chain as a list of dictionaries (one per
        filter, in the same order as ``get_filters``). Returns ``None``
        when no ``/DecodeParms`` entry is present.

        PDF allows ``/DecodeParms`` to be either a single dictionary
        (when ``/Filter`` has one entry) or an array of dictionaries (one
        per filter, with the null object ``COSNull`` standing in for "no
        params for this filter")."""
        from pypdfbox.cos import COSNull  # noqa: PLC0415 — local to avoid cycle

        parms = self._stream.get_dictionary_object(_DECODE_PARMS)
        if parms is None:
            return None
        if isinstance(parms, COSDictionary):
            return [parms]
        if isinstance(parms, COSArray):
            out: list[COSDictionary] = []
            for entry in parms:
                if isinstance(entry, COSDictionary):
                    out.append(entry)
                elif entry is None or isinstance(entry, COSNull):
                    # "No parameters for this filter" sentinel — record
                    # an empty dict so the list-index alignment with the
                    # filter chain is preserved.
                    out.append(COSDictionary())
                else:
                    raise TypeError(
                        f"unexpected /DecodeParms entry type: {type(entry).__name__}"
                    )
            return out
        raise TypeError(f"unexpected /DecodeParms type: {type(parms).__name__}")

    def set_decode_parms(
        self,
        parms: COSDictionary | Sequence[COSDictionary] | None,
    ) -> None:
        """Replace ``/DecodeParms``. Accepts ``None`` (removes the entry),
        a single ``COSDictionary`` (stored as-is — single-filter form),
        or a sequence of dictionaries (stored as a ``COSArray``)."""
        if parms is None:
            self._stream.remove_item(_DECODE_PARMS)
            return
        if isinstance(parms, COSDictionary):
            self._stream.set_item(_DECODE_PARMS, parms)
            return
        arr = COSArray(list(parms))
        self._stream.set_item(_DECODE_PARMS, arr)

    # ---------- /Metadata ----------

    def get_metadata(self) -> COSStream | None:
        """``/Metadata`` — stream-level XMP metadata, or ``None``."""
        meta = self._stream.get_dictionary_object(_METADATA)
        if meta is None:
            return None
        if isinstance(meta, COSStream):
            return meta
        raise TypeError(f"unexpected /Metadata type: {type(meta).__name__}")

    def set_metadata(self, stream: COSStream | None) -> None:
        """Set ``/Metadata`` (or remove when ``None``)."""
        if stream is None:
            self._stream.remove_item(_METADATA)
            return
        self._stream.set_item(_METADATA, stream)

    # ---------- bytes convenience ----------

    def to_byte_array(self) -> bytes:
        """Return the *decoded* body as a ``bytes``. Empty stream →
        ``b""``. Mirrors upstream ``toByteArray()``."""
        if not self._stream.has_data():
            return b""
        return self._stream.to_byte_array()


def _to_name(value: COSName | str) -> COSName:
    if isinstance(value, COSName):
        return value
    return COSName.get_pdf_name(value)
