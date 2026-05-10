from __future__ import annotations

import contextlib
import io
import logging
import os
from abc import ABC, abstractmethod
from collections.abc import Callable, Sequence
from typing import BinaryIO, Final

from pypdfbox.cos import COSArray, COSDictionary, COSName

from .decode_result import DecodeResult
from .missing_image_reader_exception import MissingImageReaderException

_LOG = logging.getLogger(__name__)
_F = COSName.get_pdf_name("F")
_FILTER = COSName.get_pdf_name("Filter")
_DP = COSName.get_pdf_name("DP")
_DECODE_PARMS = COSName.get_pdf_name("DecodeParms")


class Filter(ABC):
    """
    Abstract PDF stream filter per ISO 32000-1 §7.4.

    Implementations decode an encoded byte stream into raw bytes and
    encode raw bytes back into the encoded form. The ``parameters``
    argument carries the stream's ``/DecodeParms`` (possibly indexed
    into via ``index`` when the stream has a chain of filters with a
    parallel array of decode-parameter dictionaries).

    Mirrors `org.apache.pdfbox.filter.Filter`.
    """

    # ------------------------------------------------------------------
    # Upstream system-property constants (mirror Java statics).
    # ------------------------------------------------------------------

    #: Environment-variable name controlling the zlib deflate level used
    #: by ``FlateDecode.encode``. Mirrors
    #: ``org.apache.pdfbox.filter.Filter#SYSPROP_DEFLATELEVEL``. Java
    #: reads this via ``System.getProperty``; the Python port reads it
    #: from ``os.environ`` since Python has no system-properties facility.
    #: Valid values are ``-1`` (zlib default) through ``9`` (best
    #: compression); ``0`` means "no compression". Out-of-range values
    #: are clamped by :meth:`get_compression_level`.
    SYSPROP_DEFLATELEVEL: Final[str] = "org.apache.pdfbox.filter.deflatelevel"

    #: Environment-variable name capping the per-image buffer
    #: ``CCITTFaxDecode`` will pre-allocate. Mirrors
    #: ``org.apache.pdfbox.filter.Filter#SYSPROP_CCITTFAX_MAXBYTES``.
    SYSPROP_CCITTFAX_MAXBYTES: Final[str] = "org.apache.pdfbox.filter.ccittmaxbytes"

    @abstractmethod
    def decode(
        self,
        encoded: BinaryIO,
        decoded: BinaryIO,
        parameters: COSDictionary | None = None,
        index: int = 0,
    ) -> DecodeResult:
        """Read encoded bytes from ``encoded``, write decoded bytes to
        ``decoded``. Returns a ``DecodeResult`` whose ``parameters`` may
        be the (possibly updated) input dictionary."""

    @abstractmethod
    def encode(
        self,
        raw: BinaryIO,
        encoded: BinaryIO,
        parameters: COSDictionary | None = None,
    ) -> None:
        """Read raw bytes from ``raw``, write encoded bytes to ``encoded``."""

    # ------------------------------------------------------------------
    # Upstream parity helpers (mirror ``org.apache.pdfbox.filter.Filter``).
    # ------------------------------------------------------------------

    @staticmethod
    def decode_result(
        parameters: COSDictionary | None = None,
        decoded_byte_count: int = 0,
    ) -> DecodeResult:
        """Convenience constructor for a ``DecodeResult``.

        Mirrors ``org.apache.pdfbox.filter.Filter#createDecodeResult``
        in spirit — concrete filters use this to return a result
        carrying the (possibly mutated) parameters dictionary along
        with the count of bytes written to the decoded sink.
        """
        params = parameters if parameters is not None else COSDictionary()
        return DecodeResult(parameters=params, bytes_written=decoded_byte_count)

    @staticmethod
    def get_decode_params(
        parameters: COSDictionary | None,
        index: int,
    ) -> COSDictionary:
        """Resolve effective ``/DecodeParms`` for the filter at ``index``.

        PDF allows ``/DecodeParms`` (or its abbreviation ``/DP``) to be
        either a single dictionary — when the stream has one filter —
        or an array parallel to ``/Filter``. Missing entries return an
        empty ``COSDictionary``.

        Mirrors ``org.apache.pdfbox.filter.Filter#getDecodeParams``.
        """
        if parameters is None:
            return COSDictionary()
        for key in ("DecodeParms", "DP"):
            params = parameters.get_dictionary_object(key)
            if isinstance(params, COSDictionary):
                return params
            if isinstance(params, COSArray):
                try:
                    entry = params.get_object(index)
                except Exception:
                    entry = None
                if isinstance(entry, COSDictionary):
                    return entry
                return COSDictionary()
        return COSDictionary()

    @staticmethod
    def get_compression_level() -> int:
        """Return the zlib deflate level configured for pypdfbox.

        Reads the :data:`SYSPROP_DEFLATELEVEL` environment variable (the
        Python-side stand-in for Java system properties) and clamps the
        result to ``-1..9`` — the range zlib accepts where ``-1`` means
        "library default" (zlib's :data:`Z_DEFAULT_COMPRESSION`) and
        ``9`` means "best compression". An unset or unparseable value
        defaults to ``-1``.

        Mirrors ``org.apache.pdfbox.filter.Filter#getCompressionLevel``.
        """
        value = os.environ.get(Filter.SYSPROP_DEFLATELEVEL, "-1")
        try:
            level = int(value)
        except ValueError:
            _LOG.warning(
                "Invalid %s=%r; falling back to default (-1)",
                Filter.SYSPROP_DEFLATELEVEL,
                value,
            )
            level = -1
        return max(-1, min(9, level))

    def is_decompression_input_size_known(self) -> bool:
        """Whether the decompressed size of the input is known up front.

        Mirrors ``org.apache.pdfbox.filter.Filter#isDecompressionInputSizeKnown``.
        Defaults to ``True``; filters that may consume more bytes than
        the stream length advertises (notably ``ASCII85Decode`` and
        ``ASCIIHexDecode`` which can pad/ignore whitespace) override to
        ``False``.
        """
        return True

    # ------------------------------------------------------------------
    # Filter-aware /DecodeParms resolution (mirrors upstream's
    # ``protected COSDictionary getDecodeParams(COSDictionary, int)``).
    # ------------------------------------------------------------------

    @staticmethod
    def get_decode_params_for_filter(
        dictionary: COSDictionary | None,
        index: int,
    ) -> COSDictionary:
        """Resolve ``/DecodeParms`` consulting ``/Filter`` to validate shape.

        Mirrors upstream's ``Filter#getDecodeParams(COSDictionary, int)``
        which inspects both the ``/F`` / ``/Filter`` entry *and* the
        ``/DP`` / ``/DecodeParms`` entry to disambiguate the single-filter
        and multi-filter cases per ISO 32000-1 §7.3.8.2:

        * single-name ``/Filter`` + dict ``/DecodeParms`` → return that dict;
        * array ``/Filter`` + array ``/DecodeParms`` → return ``arr[index]``
          if it is a dictionary, otherwise an empty dictionary;
        * any other shape (mismatched name+array or array+dict) is logged
          as an error and an empty dictionary is returned. PDFBox warns
          about this case to surface malformed PDFs without aborting.

        Unlike :meth:`get_decode_params` (the lenient resolver used by
        legacy callers), this strict variant rejects a single dict on a
        multi-filter stream — that combination would otherwise route the
        same params to every filter index and silently misconfigure the
        downstream codec.
        """
        if dictionary is None:
            return COSDictionary()
        # ``get_dictionary_object(key, default)`` resolves ``key`` first
        # and falls back to ``default`` if absent — same dual-key overload
        # upstream's ``getDictionaryObject(COSName.F, COSName.FILTER)`` uses.
        filter_obj = dictionary.get_dictionary_object(_F, _FILTER)
        params_obj = dictionary.get_dictionary_object(_DP, _DECODE_PARMS)
        if isinstance(filter_obj, COSName) and isinstance(params_obj, COSDictionary):
            # PDFBOX-3932: single filter name → params is the parameter dict.
            return params_obj
        if isinstance(filter_obj, COSArray) and isinstance(params_obj, COSArray):
            if index < params_obj.size():
                try:
                    entry = params_obj.get_object(index)
                except AttributeError:
                    # COSArray.get_object is upstream-named; older shims
                    # may only expose ``get``. Fall back gracefully.
                    entry = params_obj.get(index)
                if isinstance(entry, COSDictionary):
                    return entry
        elif params_obj is not None and not (
            isinstance(filter_obj, COSArray) or isinstance(params_obj, COSArray)
        ):
            _LOG.error(
                "Expected DecodeParams to be an Array or Dictionary but found %s",
                type(params_obj).__name__,
            )
        return COSDictionary()

    # ------------------------------------------------------------------
    # Image-reader discovery (mirrors upstream's static helpers that
    # delegate to ``javax.imageio.ImageIO`` — we delegate to Pillow).
    # ------------------------------------------------------------------

    @staticmethod
    def find_image_reader(format_name: str, error_cause: str) -> Callable[..., object]:
        """Return Pillow's open-factory callable for ``format_name``.

        Mirrors ``Filter#findImageReader(String, String)``. Upstream
        iterates ``ImageIO.getImageReadersByFormatName(formatName)`` and
        returns the first non-null reader, raising
        :class:`MissingImageReaderException` when none is registered.

        The pypdfbox port consults Pillow's plugin registry — populated
        on first ``PIL.Image.init()`` — and returns the registered open
        factory (the first element of the ``Image.OPEN[fmt]`` tuple). PDF
        callers do not actually invoke this factory directly: the
        round-tripped JPEG / JPEG-2000 / TIFF / JBIG2 pipelines all open
        bytes via ``PIL.Image.open``. The helper exists for porting
        parity so direct translations of upstream guard code can resolve
        ``Filter.findImageReader("JPEG2000", ...)`` to a non-``None``
        value when the codec is available.

        Format names follow Pillow conventions (``"JPEG"``, ``"JPEG2000"``,
        ``"TIFF"``). Raises :class:`MissingImageReaderException` when no
        plugin is registered for the format.
        """
        # Local import keeps the filter module lightweight when callers
        # never reach for image-bearing filters.
        from PIL import Image

        Image.init()  # populates ID/MIME/EXTENSION tables on first call.
        plugin_id = format_name.upper()
        registered = Image.OPEN.get(plugin_id)
        if registered is not None:
            # Image.OPEN maps format → (factory, accept) tuple.
            return registered[0]
        raise MissingImageReaderException(
            f"Cannot read {format_name} image: {error_cause}"
        )

    # ------------------------------------------------------------------
    # Static filter-chain decoder (mirrors upstream's
    # ``static RandomAccessRead Filter.decode(InputStream, List<Filter>,
    #     COSDictionary, DecodeOptions, List<DecodeResult>)``).
    # ------------------------------------------------------------------

    @staticmethod
    def decode_chain(
        encoded: BinaryIO,
        filter_list: Sequence[Filter],
        parameters: COSDictionary | None = None,
        options: object | None = None,
        results: list[DecodeResult] | None = None,
    ) -> BinaryIO:
        """Apply a chain of filters to ``encoded`` and return the decoded buffer.

        Mirrors ``Filter.decode(InputStream, List<Filter>, COSDictionary,
        DecodeOptions, List<DecodeResult>)`` (upstream Java lines 241-309).
        Each filter in ``filter_list`` is invoked in turn; the output of
        filter ``i`` becomes the input of filter ``i+1``. Duplicate filter
        instances are deduplicated (preserving order) — upstream behaviour
        for malformed streams that double-list a filter, e.g.
        ``[/FlateDecode /FlateDecode]`` when only one application is
        intended.

        ``options`` is accepted for upstream signature parity. The
        DecodeOptions value type is not yet ported, so this argument is
        currently ignored — the four-arg :meth:`decode` of each filter is
        called directly. Filters' single-shot ``decode`` already handles
        the parameters dictionary it needs.

        ``results``, if provided, is appended to with the per-filter
        :class:`DecodeResult`. Returns a seekable buffer positioned at
        offset 0 holding the fully-decoded bytes.

        Raises :class:`ValueError` when ``filter_list`` is empty (upstream
        raises ``IllegalArgumentException``).
        """
        if not filter_list:
            raise ValueError("Empty filterList")
        # Deduplicate while preserving order — upstream uses a HashSet
        # round-trip and warns when duplicates are removed.
        if len(filter_list) > 1 and len(set(filter_list)) != len(filter_list):
            seen: list[Filter] = []
            for filt in filter_list:
                if filt not in seen:
                    seen.append(filt)
            filter_list = seen
            _LOG.warning("Removed duplicated filter entries")
        params = parameters if parameters is not None else COSDictionary()
        current_input: BinaryIO = encoded
        buffer = io.BytesIO()
        for index, filt in enumerate(filter_list):
            buffer = io.BytesIO()
            try:
                result = filt.decode(current_input, buffer, params, index)
            finally:
                # Mirror upstream's ``IOUtils.closeQuietly(input)`` —
                # never propagate a close-time error. The original
                # caller-supplied ``encoded`` stream is closed too, which
                # matches Java behavior.
                with contextlib.suppress(Exception):
                    current_input.close()
            if results is not None:
                results.append(result)
            buffer.seek(0)
            current_input = buffer
        buffer.seek(0)
        return buffer

    @staticmethod
    def find_raster_reader(format_name: str, error_cause: str) -> Callable[..., object]:
        """Return Pillow's open-factory for raster decoding of ``format_name``.

        Mirrors ``Filter#findRasterReader(String, String)``. In Java this
        is distinct from :meth:`find_image_reader` because some Java
        ``ImageReader``\\ s decode only fully-rendered ``BufferedImage``\\ s
        and reject raw raster access (``canReadRaster()`` returns false).
        Pillow's plugins all expose raster access uniformly via
        ``Image.tobytes()``, so the two helpers are functionally
        identical here — kept distinct for porting parity so direct
        translations of upstream code resolve.
        """
        return Filter.find_image_reader(format_name, error_cause)
