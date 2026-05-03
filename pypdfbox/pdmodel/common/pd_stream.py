from __future__ import annotations

from collections.abc import Iterable, Sequence
from contextlib import suppress
from typing import TYPE_CHECKING, BinaryIO

from pypdfbox.cos import COSArray, COSDictionary, COSDocument, COSName, COSStream

if TYPE_CHECKING:
    from pypdfbox.pdmodel.common.filespecification import PDFileSpecification
    from pypdfbox.pdmodel.common.pd_metadata import PDMetadata
    from pypdfbox.pdmodel.pd_document import PDDocument


_FILTER: COSName = COSName.FILTER  # type: ignore[attr-defined]
_LENGTH: COSName = COSName.LENGTH  # type: ignore[attr-defined]
_METADATA: COSName = COSName.METADATA  # type: ignore[attr-defined]
_DL: COSName = COSName.get_pdf_name("DL")
_DECODE_PARMS: COSName = COSName.get_pdf_name("DecodeParms")
_DP: COSName = COSName.get_pdf_name("DP")
_F: COSName = COSName.get_pdf_name("F")
_FFILTER: COSName = COSName.get_pdf_name("FFilter")
_FDECODE_PARMS: COSName = COSName.get_pdf_name("FDecodeParms")


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

    def get_cos_stream(self) -> COSStream:
        """Alias for :meth:`get_cos_object` — mirrors upstream
        ``getCOSStream()``."""
        return self._stream

    def get_stream(self) -> COSStream:
        """Alias for :meth:`get_cos_object` — mirrors upstream
        ``getStream()``."""
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

    def set_length(self, length: int) -> None:
        """Write ``/Length`` directly. Mirrors upstream ``setLength(int)``.

        Note: PDF writers re-compute ``/Length`` from the actual encoded
        body on serialisation, so this setter is mostly a placeholder for
        round-trip parity with upstream. Callers that just want the
        encoded length to reflect the body should leave ``/Length`` alone
        and let the writer fill it in."""
        self._stream.set_int(_LENGTH, int(length))

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

    def is_filter_undefined(self) -> bool:
        """``True`` when ``/Filter`` is absent from the dictionary.
        Mirrors upstream ``isFilterUndefined()`` — used by callers that
        need to skip filter wiring when the stream has no encoding chain."""
        return not self._stream.contains_key(_FILTER)

    def has_filter(self, name: COSName | str) -> bool:
        """``True`` when ``name`` appears in the ``/Filter`` chain.

        Accepts either a ``COSName`` or a plain ``str`` filter name (the
        string form is resolved via :meth:`COSName.get_pdf_name`). Useful
        for callers that branch on the presence of a specific encoding
        filter without iterating the chain manually."""
        target = _to_name(name)
        return target in self.get_filters()

    def get_first_filter(self) -> COSName | None:
        """Return the first ``/Filter`` entry, or ``None`` when the chain
        is empty / absent.

        Convenience for the (very common) single-filter case where callers
        otherwise have to write ``self.get_filters()[0] if
        self.get_filters() else None``."""
        filters = self.get_filters()
        return filters[0] if filters else None

    def get_filters_as_strings(self) -> list[str]:
        """``/Filter`` chain as a list of plain filter-name strings (no
        leading slash). Empty when absent.

        Mirrors the spelled-out upstream pattern ``getFilters().stream().map(
        COSName::getName).collect(...)`` and complements
        :meth:`get_file_filters_as_strings`. Useful for callers that compare
        filter identifiers as strings (e.g. matching against the keys of a
        ``Filter`` registry)."""
        return [f.name for f in self.get_filters()]

    # ---------- decode parameters ----------

    def get_decode_parms(self) -> list[COSDictionary] | None:
        """``/DecodeParms`` chain as a list of dictionaries (one per
        filter, in the same order as ``get_filters``). Returns ``None``
        when neither ``/DecodeParms`` nor ``/DP`` is present.

        PDF allows ``/DecodeParms`` to be either a single dictionary
        (when ``/Filter`` has one entry) or an array of dictionaries (one
        per filter, with the null object ``COSNull`` standing in for "no
        params for this filter").

        Per PDF Reference 1.5 implementation note 7, some producers spell
        the entry ``/DP`` rather than ``/DecodeParms``; we fall back to
        ``/DP`` when the canonical key is absent. Mirrors upstream
        ``getDecodeParms()``."""
        from pypdfbox.cos import COSNull  # noqa: PLC0415 — local to avoid cycle

        parms = self._stream.get_dictionary_object(_DECODE_PARMS)
        if parms is None:
            parms = self._stream.get_dictionary_object(_DP)
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
        """``/Metadata`` — stream-level XMP metadata, or ``None``.

        Returns the raw ``COSStream``; callers that want the typed
        :class:`PDMetadata` wrapper should construct one explicitly
        (``PDMetadata(stream.get_metadata())``). Upstream returns
        ``PDMetadata`` directly, but we keep ``COSStream`` for parity
        with prior call-sites that compare-by-identity against the
        stream they set."""
        meta = self._stream.get_dictionary_object(_METADATA)
        if meta is None:
            return None
        if isinstance(meta, COSStream):
            return meta
        raise TypeError(f"unexpected /Metadata type: {type(meta).__name__}")

    def has_metadata(self) -> bool:
        """``True`` when the wrapped stream carries a ``/Metadata`` entry
        whose value is a ``COSStream``.

        Mirrors the natural "is this stream tagged with stream-level XMP"
        predicate; complements :meth:`get_metadata` which returns the
        ``COSStream`` itself (or ``None``). Returns ``False`` for the
        ``COSNull`` case that upstream's ``getMetadata`` allows."""
        return self.get_metadata() is not None

    def set_metadata(self, stream: PDMetadata | COSStream | None) -> None:
        """Set ``/Metadata`` (or remove when ``None``). Accepts a typed
        :class:`PDMetadata` (the underlying ``COSStream`` is recorded) or
        a raw ``COSStream``. Mirrors upstream ``setMetadata(PDMetadata)``
        with a Pythonic widening to ``COSStream`` for callers that already
        hold the raw object."""
        if stream is None:
            self._stream.remove_item(_METADATA)
            return
        if isinstance(stream, COSStream):
            self._stream.set_item(_METADATA, stream)
            return
        # PDMetadata (or any PDStream subclass) — unwrap to COSStream.
        self._stream.set_item(_METADATA, stream.get_cos_object())

    # ---------- /F external file spec ----------

    def get_file(self) -> PDFileSpecification | None:
        """``/F`` — external file specification. Returns ``None`` when the
        entry is absent. Mirrors upstream
        ``getFile() : PDFileSpecification``."""
        from pypdfbox.pdmodel.common.filespecification import (  # noqa: PLC0415
            PDFileSpecification,
        )

        base = self._stream.get_dictionary_object(_F)
        if base is None:
            return None
        return PDFileSpecification.create_fs(base)

    def set_file(self, file: PDFileSpecification | None) -> None:
        """Write the ``/F`` external file specification entry. Mirrors
        upstream ``setFile(PDFileSpecification)``."""
        if file is None:
            self._stream.remove_item(_F)
            return
        self._stream.set_item(_F, file.get_cos_object())

    def is_external(self) -> bool:
        """``True`` when this stream references its body via the ``/F``
        external file specification rather than carrying an inline body.

        Convenience predicate complementing :meth:`get_file`; matches the
        natural "is this an external stream" check that callers otherwise
        write as ``stream.get_file() is not None``. Note this only checks
        for the *presence* of ``/F`` — it does not validate that the
        referenced file actually exists on disk."""
        return self._stream.contains_key(_F)

    def get_file_filters(self) -> list[COSName]:
        """``/FFilter`` chain — filter chain to apply when the body is
        sourced from the external file referenced by ``/F``. Same shape
        rules as ``/Filter``. Empty when absent. Mirrors upstream
        ``getFileFilters() : List<COSName>``."""
        f = self._stream.get_dictionary_object(_FFILTER)
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
                        f"non-name entry in /FFilter array: {type(entry).__name__}"
                    )
            return out
        raise TypeError(f"unexpected /FFilter type: {type(f).__name__}")

    def get_file_filters_as_strings(self) -> list[str]:
        """``/FFilter`` chain as a list of plain filter-name strings (no
        leading slash). Empty when absent.

        Matches the *exact* upstream return shape of ``getFileFilters()
        : List<String>``, which we deliberately diverge from in
        :meth:`get_file_filters` (where we return ``list[COSName]`` for
        symmetry with :meth:`get_filters`). Use this accessor when you
        need byte-for-byte parity with upstream's string-form output."""
        return [f.name for f in self.get_file_filters()]

    def set_file_filters(
        self,
        filters: COSName | str | Iterable[COSName | str] | None,
    ) -> None:
        """Replace ``/FFilter`` — the filter chain applied when the body
        is sourced from the external file referenced by ``/F``. Same shape
        rules as :meth:`set_filters`. Mirrors upstream
        ``setFileFilters(List<COSName>)``."""
        if filters is None:
            self._stream.remove_item(_FFILTER)
            return
        if isinstance(filters, (COSName, str)):
            names = [_to_name(filters)]
        else:
            names = [_to_name(n) for n in filters]
        arr = COSArray(names)
        self._stream.set_item(_FFILTER, arr)

    def get_file_decode_parms(self) -> list[COSDictionary] | None:
        """``/FDecodeParms`` — decode-parameter chain paired with
        ``/FFilter`` (one dict per file-filter, in matching order).
        Returns ``None`` when absent. Mirrors upstream
        ``getFileDecodeParams() : List<COSDictionary>``."""
        from pypdfbox.cos import COSNull  # noqa: PLC0415 — local to avoid cycle

        parms = self._stream.get_dictionary_object(_FDECODE_PARMS)
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
                    out.append(COSDictionary())
                else:
                    raise TypeError(
                        f"unexpected /FDecodeParms entry type: "
                        f"{type(entry).__name__}"
                    )
            return out
        raise TypeError(f"unexpected /FDecodeParms type: {type(parms).__name__}")

    def set_file_decode_parms(
        self,
        parms: COSDictionary | Sequence[COSDictionary] | None,
    ) -> None:
        """Replace ``/FDecodeParms`` — decode-parameter chain paired with
        ``/FFilter``. Same shape rules as :meth:`set_decode_parms`. Mirrors
        upstream ``setFileDecodeParams(List<COSDictionary>)``."""
        if parms is None:
            self._stream.remove_item(_FDECODE_PARMS)
            return
        if isinstance(parms, COSDictionary):
            self._stream.set_item(_FDECODE_PARMS, parms)
            return
        arr = COSArray(list(parms))
        self._stream.set_item(_FDECODE_PARMS, arr)

    def get_file_decode_params(self) -> list[COSDictionary] | None:
        """Snake_case spelling of upstream ``getFileDecodeParams()`` — note
        that upstream is inconsistent (``getDecodeParms`` vs.
        ``getFileDecodeParams``) so we provide both spellings of the
        ``/FDecodeParms`` accessor. Delegates to
        :meth:`get_file_decode_parms`."""
        return self.get_file_decode_parms()

    def set_file_decode_params(
        self,
        parms: COSDictionary | Sequence[COSDictionary] | None,
    ) -> None:
        """Snake_case spelling of upstream ``setFileDecodeParams(List)``.
        Delegates to :meth:`set_file_decode_parms`."""
        self.set_file_decode_parms(parms)

    # ---------- bytes convenience ----------

    def to_byte_array(self) -> bytes:
        """Return the *decoded* body as a ``bytes``. Empty stream →
        ``b""``. Mirrors upstream ``toByteArray()``."""
        if not self._stream.has_data():
            return b""
        return self._stream.to_byte_array()

    def is_empty(self) -> bool:
        """``True`` when the wrapped ``COSStream`` carries no body bytes.

        Useful for short-circuiting filter / decode pipelines that would
        otherwise create empty ``BytesIO`` handles. Note this checks the
        live raw buffer — a stream whose ``/Length`` was set but whose
        body was never populated still reports ``True``."""
        return not self._stream.has_data()


def _to_name(value: COSName | str) -> COSName:
    if isinstance(value, COSName):
        return value
    return COSName.get_pdf_name(value)
