from __future__ import annotations

import io
import os
from pathlib import Path
from typing import TYPE_CHECKING, BinaryIO

from .ttf_data_stream import (
    MemoryTTFDataStream,
    RandomAccessReadDataStream,
    TTFDataStream,
)
from .true_type_font import TrueTypeFont

if TYPE_CHECKING:
    from pypdfbox.io.random_access_read import RandomAccessRead


# SFNT scaler-type tags (32-bit big-endian magic at offset 0).
_TAG_TRUE_TYPE: int = 0x00010000  # TrueType outlines
_TAG_OPEN_TYPE_CFF: int = 0x4F54544F  # 'OTTO' — OpenType with CFF outlines
_TAG_TRUE: int = 0x74727565  # 'true' — Apple TrueType
_TAG_TYP1: int = 0x74797031  # 'typ1' — old Apple Type 1 housed in SFNT


class TTFParser:
    """Parser for the TrueType-flavoured SFNT container.

    Mirrors ``org.apache.fontbox.ttf.TTFParser``. The actual SFNT
    directory + table parsing is delegated to fontTools' ``TTFont``
    (library-first per CLAUDE.md): re-implementing TTF/OTF parsing in
    pure Python is exactly what fontTools (MIT) is for. The ``TTFParser``
    class is preserved as the public entry point so PDFBox-shaped code
    that does ``new TTFParser().parse(...)`` ports across without
    rewiring.

    The constructor flags mirror upstream:

    * ``is_embedded`` — when ``True`` the parser tolerates fonts that
      omit otherwise-required tables (some embedded subsets in PDFs do
      this). For the fontTools backend this only affects the validation
      hook in :meth:`_check_tables`; the underlying decode is unchanged.
    * ``parse_on_demand`` — when ``True`` callers expect lazy table
      decoding. fontTools' ``TTFont(lazy=True)`` already does this, and
      the wrapper :class:`TrueTypeFont` constructs its underlying font
      with ``lazy=True``, so this flag is recorded but does not change
      observable behaviour today.
    """

    def __init__(
        self,
        is_embedded: bool = False,  # noqa: FBT001, FBT002 — mirror upstream signature
        parse_on_demand: bool = True,  # noqa: FBT001, FBT002
    ) -> None:
        self._is_embedded: bool = is_embedded
        self._parse_on_demand: bool = parse_on_demand

    # ---------- public properties (PDFBox-equivalent fields) -----------

    @property
    def is_embedded(self) -> bool:
        return self._is_embedded

    @property
    def parse_on_demand(self) -> bool:
        return self._parse_on_demand

    # ---------- parse() entry points ----------------------------------
    # PDFBox exposes overloaded `parse(File)`, `parse(InputStream)`,
    # `parse(RandomAccessRead)`. Python doesn't overload, so a single
    # entry point dispatches on the concrete input type.

    def parse(
        self,
        source: bytes
        | bytearray
        | memoryview
        | str
        | os.PathLike[str]
        | BinaryIO
        | TTFDataStream
        | RandomAccessRead,
    ) -> TrueTypeFont:
        """Parse ``source`` into a :class:`TrueTypeFont`.

        Accepts any of:

        * ``bytes`` / ``bytearray`` / ``memoryview`` — raw SFNT bytes.
        * ``str`` / ``os.PathLike`` — filesystem path to a TTF/OTF file.
        * file-like binary stream (anything with ``.read()``).
        * an existing :class:`TTFDataStream` (returned as-is).
        * an existing :class:`pypdfbox.io.RandomAccessRead`.
        """
        stream = self._coerce_to_data_stream(source)
        font = self._parse_data_stream(stream)
        self._check_tables(font)
        return font

    def parse_embedded(
        self,
        source: bytes
        | bytearray
        | memoryview
        | str
        | os.PathLike[str]
        | BinaryIO
        | TTFDataStream
        | RandomAccessRead,
    ) -> TrueTypeFont:
        """Parse ``source`` as a font embedded inside a PDF.

        Mirrors upstream ``TTFParser.parseEmbedded(InputStream)``:
        flips the parser into embedded mode (``is_embedded = True``)
        for the duration of the call so the post-parse table check
        tolerates the partial table sets typical of embedded subsets,
        then delegates to :meth:`parse`. The flag is left ``True``
        afterwards (matching upstream's ``this.isEmbedded = true``
        side-effect).
        """
        self._is_embedded = True
        return self.parse(source)

    # ---------- factory hook for OTF subclass --------------------------

    def _new_font(self, data: TTFDataStream) -> TrueTypeFont:
        """Produce the concrete font instance.

        Overridden by :class:`OTFParser` to return :class:`OpenTypeFont`.
        """
        return TrueTypeFont(data)

    def _allow_cff(self) -> bool:
        """Whether CFF outlines (an ``OTTO``-flavoured SFNT) are
        acceptable inputs to this parser.

        Mirrors upstream ``TTFParser.allowCFF()`` (a protected
        no-arg hook). The base ``TTFParser`` rejects CFF; the
        :class:`OTFParser` subclass overrides this to return
        ``True``. Kept as a hook so future code paths that need to
        gate on the setting (e.g. when a generic SFNT loader has to
        decide between TTF/OTF parsers) stay parity-compatible with
        upstream code.
        """
        return False

    # ---------- internals ----------------------------------------------

    def _coerce_to_data_stream(self, source: object) -> TTFDataStream:
        # 1. Already a TTFDataStream — pass through.
        if isinstance(source, TTFDataStream):
            return source
        # 2. Path-like — read the whole file. Lazy mode will re-decode
        #    individual tables on demand from the in-memory copy.
        if isinstance(source, (str, os.PathLike)):
            data = Path(source).read_bytes()
            return MemoryTTFDataStream(data)
        # 3. Raw bytes-like.
        if isinstance(source, (bytes, bytearray, memoryview)):
            return MemoryTTFDataStream(bytes(source))
        # 4. RandomAccessRead — wrap with the stream adapter that already
        #    drains it into memory.
        from pypdfbox.io.random_access_read import RandomAccessRead  # noqa: PLC0415

        if isinstance(source, RandomAccessRead):
            return RandomAccessReadDataStream(source)
        # 5. File-like binary stream — drain it.
        if hasattr(source, "read"):
            data = source.read()
            if not isinstance(data, (bytes, bytearray)):
                msg = f"file-like source must yield bytes, got {type(data).__name__}"
                raise TypeError(msg)
            return MemoryTTFDataStream(bytes(data))
        msg = f"unsupported source type for TTFParser.parse: {type(source).__name__}"
        raise TypeError(msg)

    def _parse_data_stream(self, data: TTFDataStream) -> TrueTypeFont:
        """Validate the SFNT magic before handing off to fontTools.

        The actual directory walk + per-table decode happens inside the
        :class:`TrueTypeFont` constructor (which builds a fontTools
        ``TTFont``); this method just gates on the scaler type so an
        ``OTFParser`` correctly rejects a bare TTF and vice versa.
        """
        raw = data.get_original_data()
        if len(raw) < 4:
            msg = f"SFNT stream too short: {len(raw)} bytes"
            raise OSError(msg)
        # Peek the 32-bit scaler type — do not consume the stream
        # position so fontTools sees the file from offset 0.
        scaler = int.from_bytes(raw[:4], "big", signed=False)
        self._check_scaler_type(scaler)
        return self._new_font(data)

    def _check_scaler_type(self, scaler: int) -> None:
        """Reject a stream whose SFNT magic is not a TTF flavour.

        Subclasses (OTFParser) override to accept ``OTTO`` instead.
        """
        if scaler in (_TAG_TRUE_TYPE, _TAG_TRUE, _TAG_TYP1):
            return
        if scaler == _TAG_OPEN_TYPE_CFF:
            msg = (
                "Stream has 'OTTO' (OpenType/CFF) magic; "
                "use OTFParser to parse this font"
            )
            raise OSError(msg)
        msg = f"unsupported SFNT scaler type: 0x{scaler:08X}"
        raise OSError(msg)

    def _check_tables(self, font: TrueTypeFont) -> None:
        """Mandatory-table presence check.

        Mirrors upstream's ``checkTables``: when ``is_embedded`` is
        ``False``, the font must carry the standard required tables
        (``head``, ``hhea``, ``maxp``, ``hmtx``, ``post``, ``name``,
        ``cmap``). Embedded PDF font subsets often omit some, so the
        check is skipped in that mode.
        """
        if self._is_embedded:
            return
        required = ("head", "hhea", "maxp", "hmtx", "post", "name", "cmap")
        missing = [tag for tag in required if not font.has_table(tag)]
        if missing:
            msg = f"font missing required SFNT tables: {missing}"
            raise OSError(msg)


__all__ = ["TTFParser"]
