from __future__ import annotations

import contextlib
import os
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, BinaryIO, Union

from pypdfbox.io.random_access_read_buffer import RandomAccessReadBuffer
from pypdfbox.io.random_access_read_buffered_file import RandomAccessReadBufferedFile

from .otf_parser import OTFParser
from .random_access_read_unbuffered_data_stream import (
    RandomAccessReadUnbufferedDataStream,
)
from .true_type_font_headers_processor import TrueTypeFontHeadersProcessor
from .true_type_font_processor import TrueTypeFontProcessor
from .ttf_data_stream import RandomAccessReadDataStream, TTFDataStream
from .ttf_parser import TTFParser

if TYPE_CHECKING:
    from pypdfbox.io.random_access_read import RandomAccessRead

    from .true_type_font import TrueTypeFont
    from .ttf_parser import FontHeaders


_TTC_MAGIC: str = "ttcf"
_OTF_SCALER_TAG: str = "OTTO"

# Upstream's sanity bound on numFonts (``TrueTypeCollection.java`` line
# 82). Anything outside 1..1024 raises — the upstream JUnit test
# (``TrueTypeFontCollectionTest.testNumberOfFonts``) deliberately
# probes a value of ``0x7FFFFFFF`` to make sure the check fires.
_MAX_FONTS: int = 1024


# Type aliases for the two processor-style callbacks. Upstream uses Java
# functional interfaces (``@FunctionalInterface``); Python users can
# pass either a class implementing the ABC or a bare callable. The
# Union types here mirror that ergonomic.
_FontCallback = Union[  # noqa: UP007 — keep ``Union`` for the forward-ref strings
    TrueTypeFontProcessor,
    Callable[["TrueTypeFont"], None],
]
_HeadersCallback = Union[  # noqa: UP007 — keep ``Union`` for the forward-ref strings
    TrueTypeFontHeadersProcessor,
    Callable[["FontHeaders"], None],
]


class TrueTypeCollection:
    """A TrueType / OpenType font collection (``.ttc`` file).

    Mirrors ``org.apache.fontbox.ttf.TrueTypeCollection``
    (``TrueTypeCollection.java`` lines 36-218). Despite the historical
    name, a "TTC" may carry either TrueType (``glyf``-flavoured) or
    OpenType (``CFF``-flavoured) fonts; each font in the collection is
    parsed with the right parser subclass on demand.

    Library-first note: pypdfbox can lean on ``fontTools.ttLib.TTCollection``
    for a one-shot parse of every font in the file. Upstream's design
    is finer-grained — it parses the TTC directory itself, then defers
    each font's table-directory walk until the caller requests a font
    by index or name — so we mirror that structure (read the header,
    cache ``font_offsets``, parse on demand) rather than slurping the
    whole collection via fontTools eagerly. The per-font parser is
    pypdfbox's :class:`TTFParser` / :class:`OTFParser` (already
    library-first via fontTools), so binary CFF / glyf decoding still
    goes through fontTools — no reimplementation.

    The class implements the context-manager protocol so callers can
    use it with ``with``; :meth:`close` releases the underlying
    :class:`TTFDataStream`.
    """

    def __init__(  # noqa: PLR0912 — dispatch tree mirrors upstream's three constructors
        self,
        source: TTFDataStream
        | RandomAccessRead
        | bytes
        | bytearray
        | memoryview
        | str
        | os.PathLike[str]
        | BinaryIO,
    ) -> None:
        """Create a collection from a TTC file, stream, or pre-loaded data.

        Upstream provides three public constructors:

        * ``TrueTypeCollection(File)`` — file on disk
          (``TrueTypeCollection.java`` lines 48-51): wraps a
          :class:`RandomAccessReadBufferedFile` and a
          :class:`RandomAccessReadDataStream`.
        * ``TrueTypeCollection(InputStream)`` — generic stream
          (lines 59-62): drains via :class:`RandomAccessReadBuffer`.
        * ``TrueTypeCollection(TTFDataStream)`` — private (lines 70-98)
          shared by both: parses the TTC header and caches the
          per-font byte offsets.

        Python has no overloading so a single constructor dispatches on
        the runtime type of ``source``. The dispatch tree matches
        upstream's behaviour exactly.
        """
        if isinstance(source, TTFDataStream):
            self._stream: TTFDataStream = source
        elif isinstance(source, (bytes, bytearray, memoryview)):
            self._stream = RandomAccessReadDataStream(bytes(source))
        elif isinstance(source, (str, os.PathLike)):
            backing = RandomAccessReadBufferedFile(Path(source))
            try:
                self._stream = RandomAccessReadDataStream(backing)
            finally:
                # Upstream's file constructor passes ``closeAfterReading
                # = true`` to ``createBufferedDataStream``: the random
                # access read is consumed eagerly into the data stream
                # and then released. We mirror that.
                backing.close()
        elif hasattr(source, "length") and hasattr(source, "read_into"):
            # Any RandomAccessRead-shaped object.
            self._stream = RandomAccessReadDataStream(source)
        else:
            # File-like / InputStream — drain via RandomAccessReadBuffer
            # exactly as upstream does (``TrueTypeCollection.java``
            # lines 59-62).
            buf = RandomAccessReadBuffer(source)
            try:
                self._stream = RandomAccessReadDataStream(buf)
            finally:
                buf.close()

        # --- parse TTC header (TrueTypeCollection.java lines 70-98) ---
        tag = self._stream.read_tag()
        if tag != _TTC_MAGIC:
            msg = "Missing TTC header"
            raise OSError(msg)
        version = self._stream.read32_fixed()
        num_fonts = int(self._stream.read_unsigned_int())
        if num_fonts <= 0 or num_fonts > _MAX_FONTS:
            msg = f"Invalid number of fonts {num_fonts}"
            raise OSError(msg)
        self._num_fonts: int = num_fonts
        self._font_offsets: list[int] = [
            int(self._stream.read_unsigned_int()) for _ in range(num_fonts)
        ]
        if version >= 2:
            # Upstream reads three unsigned shorts (DSig tag / length /
            # offset) but discards them — "not used at this time"
            # comment (``TrueTypeCollection.java`` lines 92-97). We
            # mirror the consumption so the stream position is correct
            # for downstream reads.
            self._stream.read_unsigned_short()
            self._stream.read_unsigned_short()
            self._stream.read_unsigned_short()
        self._version: float = version

    # ---------- iteration / lookup ----------------------------------

    def process_all_fonts(self, processor: _FontCallback) -> None:
        """Run ``processor`` for each font in the collection.

        Mirrors ``void processAllFonts(TrueTypeFontProcessor)``
        (``TrueTypeCollection.java`` lines 121-128). Accepts either an
        :class:`TrueTypeFontProcessor` instance (upstream-style) or a
        bare callable taking a :class:`TrueTypeFont`.
        """
        callback = _resolve_font_callback(processor)
        for i in range(self._num_fonts):
            font = self.get_font_at_index(i)
            callback(font)

    def process_all_font_headers(
        self,
        processor: _HeadersCallback,
    ) -> None:
        """Instance-flavoured ``processAllFontHeaders`` over this collection.

        Upstream exposes only the ``static`` variant taking a ``File``
        + a processor (``TrueTypeCollection.java`` lines 136-151). The
        instance version we add here is a thin convenience that runs
        :meth:`TTFParser.parse_table_headers` over each font's slot in
        the existing stream — useful for callers that already have a
        live collection.

        The :meth:`process_all_font_headers_in_file` class method
        below preserves the exact upstream entry point name.
        """
        callback = _resolve_headers_callback(processor)
        for i in range(self._num_fonts):
            parser = self.create_font_parser_at_index_and_seek(i)
            # Slice the per-font payload — see :meth:`_extract_font_bytes`
            # for the library-first rationale. Wrapping the slice in a
            # :class:`TTCDataStream`-backed memory stream preserves the
            # "TTC parser ⇒ TTCDataStream view" type-signature parity
            # with upstream while keeping the contiguous payload the
            # fontTools-backed parser needs.
            font_bytes = self._extract_font_bytes(i)
            headers = parser.parse_table_headers(font_bytes)
            callback(headers)

    @classmethod
    def process_all_font_headers_in_file(
        cls,
        ttc_file: str | os.PathLike[str],
        processor: _HeadersCallback,
    ) -> None:
        """Header-only iteration over every font in ``ttc_file``.

        Mirrors the upstream static ``processAllFontHeaders(File,
        TrueTypeFontHeadersProcessor)`` (``TrueTypeCollection.java``
        lines 136-151). Uses :class:`RandomAccessReadUnbufferedDataStream`
        so most of the file is skipped (only the per-font directory
        headers are touched), exactly like upstream's fast path used by
        ``FileSystemFontProvider.scanFonts``.
        """
        callback = _resolve_headers_callback(processor)
        read = RandomAccessReadBufferedFile(Path(ttc_file))
        try:
            stream = RandomAccessReadUnbufferedDataStream(read)
            ttc = cls(stream)
            try:
                for i in range(ttc._num_fonts):
                    parser = ttc.create_font_parser_at_index_and_seek(i)
                    font_bytes = ttc._extract_font_bytes(i)
                    headers = parser.parse_table_headers(font_bytes)
                    callback(headers)
            finally:
                ttc.close()
        finally:
            # ``read`` is consumed by the unbuffered data stream; closing
            # the data stream above already closes the underlying read.
            # Belt-and-braces close to match upstream's try-with-resources
            # if the inner block raised before the data stream took
            # ownership.
            with contextlib.suppress(OSError):
                read.close()

    def get_number_of_fonts(self) -> int:
        """Number of fonts in the collection.

        Convenience accessor — upstream keeps ``numFonts`` package-
        private but every Java caller that touches it does so through
        ``getNumberOfFonts``-shaped code. The Python wrapper exposes
        the value explicitly so callers don't need to reach into
        ``_num_fonts``.
        """
        return self._num_fonts

    def get_num_fonts(self) -> int:
        """Shorter convenience accessor — alias of
        :meth:`get_number_of_fonts`. Both return the value upstream's
        package-private ``numFonts`` field holds.
        """
        return self._num_fonts

    def get_font_offsets(self) -> list[int]:
        """Per-font byte offsets into the TTC container.

        Same rationale as :meth:`get_number_of_fonts` — upstream
        exposes the array indirectly via the public methods, we mirror
        the read shape for parity tooling.
        """
        return list(self._font_offsets)

    def get_font_by_name(self, name: str) -> TrueTypeFont | None:
        """Find a font by its PostScript name.

        Mirrors ``TrueTypeFont getFontByName(String)``
        (``TrueTypeCollection.java`` lines 182-193). Linear scan; per-
        font directories are parsed lazily so this only does as much
        work as needed to reach the matching font.
        """
        for i in range(self._num_fonts):
            font = self.get_font_at_index(i)
            if font.get_name() == name:
                return font
        return None

    # ---------- internals -------------------------------------------

    def get_font_at_index(self, idx: int) -> TrueTypeFont:
        """Mirror the upstream private ``getFontAtIndex``
        (``TrueTypeCollection.java`` lines 153-157).

        Library-first detail: upstream's :class:`TTFParser` walks the
        SFNT directory byte-by-byte off the data stream at the seeked
        position. pypdfbox's parser delegates to fontTools' ``TTFont``,
        which needs a contiguous bytes payload starting at the SFNT
        scaler tag. We slice the per-font bytes out of the host TTC
        using fontTools' ``TTCollection`` (the matching reader for
        ``TTCollection.save``) and hand each font to the right parser.
        Behaviour observable to PDFBox-shaped callers (TTF for non-OTTO
        scaler, OpenType for OTTO) is preserved.
        """
        parser = self.create_font_parser_at_index_and_seek(idx)
        font_bytes = self._extract_font_bytes(idx)
        return parser.parse(font_bytes)

    def _extract_font_bytes(self, idx: int) -> bytes:
        """Materialise the SFNT payload of the font at ``idx``.

        Uses ``fontTools.ttLib.TTCollection`` to re-read the host TTC
        and dump the single font as a standalone SFNT stream. Cached
        per index so repeated lookups (e.g. ``get_font_by_name`` plus
        ``process_all_fonts``) do not re-pay the cost.
        """
        if not hasattr(self, "_font_byte_cache"):
            self._font_byte_cache: dict[int, bytes] = {}
        if idx in self._font_byte_cache:
            return self._font_byte_cache[idx]

        # Library-first: lean on fontTools to do the directory slicing.
        # We need the raw TTC bytes — re-materialise them from the
        # underlying data stream so we don't fight the abstract reader.
        import io as _io  # noqa: PLC0415

        from fontTools.ttLib import TTCollection  # type: ignore[import-untyped]  # noqa: PLC0415

        ttc_bytes = self._stream.get_original_data()
        # Upstream FontBox treats the 4-byte TTC version purely as a DSIG
        # presence marker: it is read via ``read32Fixed`` and the only
        # decision it drives is ``version >= 2`` (consume the trailing DSIG
        # tag/length/offset). FontBox never gates on the version being one of
        # the two canonical values, so a header carrying ``0x00000000`` /
        # ``0xFFFFFFFF`` / any other version still parses and yields its
        # fonts. fontTools' ``TTCollection`` reader is stricter — it asserts
        # ``version in (0x00010000, 0x00020000)`` and crashes otherwise. We
        # already consumed/recorded the real version (``self._version``) and
        # the DSIG fields in the header parse, so before handing the bytes to
        # the fontTools slicer we normalise the version DWORD to the
        # canonical value matching the DSIG decision we already made. This
        # keeps per-font offset slicing intact while removing the spurious
        # version gate FontBox does not impose. (Wave 1530 differential fuzz.)
        ttc_bytes = self._normalise_ttc_version(ttc_bytes)
        collection = TTCollection(_io.BytesIO(ttc_bytes))
        if not 0 <= idx < len(collection.fonts):
            msg = f"font index out of range: {idx} (have {len(collection.fonts)})"
            raise IndexError(msg)
        sink = _io.BytesIO()
        collection.fonts[idx].save(sink)
        payload = sink.getvalue()
        self._font_byte_cache[idx] = payload
        return payload

    def _normalise_ttc_version(self, ttc_bytes: bytes) -> bytes:
        """Rewrite the TTC version DWORD to a fontTools-accepted value.

        FontBox does not validate the TTC version field (it only checks
        ``version >= 2`` to decide whether DSIG fields follow), but
        fontTools' ``TTCollection`` asserts the version is one of the two
        canonical values. We already parsed the real version into
        :attr:`_version`; pick the canonical DWORD that preserves the same
        DSIG decision so fontTools' slicer accepts a header FontBox would
        have tolerated. Bytes that are too short to hold the version field
        are returned unchanged (the constructor would already have failed).
        """
        if len(ttc_bytes) < 8:
            return ttc_bytes
        canonical = 0x00020000 if self._version >= 2 else 0x00010000
        buf = bytearray(ttc_bytes)
        buf[4:8] = canonical.to_bytes(4, "big")
        return bytes(buf)

    def create_font_parser_at_index_and_seek(self, idx: int) -> TTFParser:
        """Mirror the upstream private ``createFontParserAtIndexAndSeek``
        (``TrueTypeCollection.java`` lines 159-173).

        Seeks the underlying stream to the start of the font at
        ``idx``, peeks the four-byte scaler tag to decide between TTF
        and OTF, then re-seeks so the caller can start parsing.
        """
        if not 0 <= idx < self._num_fonts:
            msg = f"font index out of range: {idx} (have {self._num_fonts})"
            raise IndexError(msg)
        offset = self._font_offsets[idx]
        self._stream.seek(offset)
        tag = self._stream.read_tag()
        if tag == _OTF_SCALER_TAG:
            parser: TTFParser = OTFParser(is_embedded=False)
        else:
            parser = TTFParser(is_embedded=False)
        self._stream.seek(offset)
        return parser

    @staticmethod
    def create_buffered_data_stream(
        random_access_read: RandomAccessRead,
        close_after_reading: bool = True,
    ) -> TTFDataStream:
        """Mirror upstream's private ``createBufferedDataStream``
        (``TrueTypeCollection.java`` L100-118).

        Builds a :class:`RandomAccessReadDataStream` that buffers the
        contents of ``random_access_read``. When ``close_after_reading``
        is true, the underlying random-access read is released as soon
        as the data stream has slurped its bytes — matching the upstream
        contract used by the file-based constructor.
        """
        try:
            return RandomAccessReadDataStream(random_access_read)
        finally:
            if close_after_reading:
                with contextlib.suppress(OSError):
                    random_access_read.close()

    # ---------- close / context-manager ----------------------------

    def close(self) -> None:
        """Release the underlying :class:`TTFDataStream`.

        Mirrors ``void close()`` (``TrueTypeCollection.java`` lines
        213-217).
        """
        self._stream.close()

    def __enter__(self) -> TrueTypeCollection:
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()


# ----------------------------------------------------------------------
# Helpers — collapse the "ABC or bare callable" dual signature into one
# callable so the rest of the class doesn't carry the dispatch noise.

def _resolve_font_callback(
    processor: _FontCallback,
) -> Callable[[TrueTypeFont], None]:
    if isinstance(processor, TrueTypeFontProcessor):
        return processor.process
    return processor


def _resolve_headers_callback(
    processor: _HeadersCallback,
) -> Callable[[FontHeaders], None]:
    if isinstance(processor, TrueTypeFontHeadersProcessor):
        return processor.process
    return processor


__all__ = ["TrueTypeCollection"]
