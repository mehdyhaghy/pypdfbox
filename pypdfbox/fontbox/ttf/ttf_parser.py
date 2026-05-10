from __future__ import annotations

import contextlib
import os
from pathlib import Path
from typing import TYPE_CHECKING, BinaryIO

from .true_type_font import TrueTypeFont
from .ttf_data_stream import (
    MemoryTTFDataStream,
    RandomAccessReadDataStream,
    TTFDataStream,
)
from .ttf_table import TTFTable

if TYPE_CHECKING:
    from pypdfbox.io.random_access_read import RandomAccessRead

    from .os2_windows_metrics_table import OS2WindowsMetricsTable


# SFNT scaler-type tags (32-bit big-endian magic at offset 0).
_TAG_TRUE_TYPE: int = 0x00010000  # TrueType outlines
_TAG_OPEN_TYPE_CFF: int = 0x4F54544F  # 'OTTO' — OpenType with CFF outlines
_TAG_TRUE: int = 0x74727565  # 'true' — Apple TrueType
_TAG_TYP1: int = 0x74797031  # 'typ1' — old Apple Type 1 housed in SFNT


class FontHeaders:
    """Lightweight summary collected by :meth:`TTFParser.parse_table_headers`.

    Mirrors ``org.apache.fontbox.ttf.FontHeaders``. Used by upstream's
    ``FileSystemFontProvider.scanFonts(...)`` fast path to skip data it
    will not need; the same surface is reproduced here so PDFBox-shaped
    callers compile and behave identically.
    """

    BYTES_GCID: int = 142

    def __init__(self) -> None:
        self._error: str | None = None
        self._name: str | None = None
        self._header_mac_style: int | None = None
        self._os2_windows: OS2WindowsMetricsTable | None = None
        self._font_family: str | None = None
        self._font_sub_family: str | None = None
        self._non_otf_gcid_142: bytes | None = None
        self._is_otf_and_post_script: bool = False
        self._otf_registry: str | None = None
        self._otf_ordering: str | None = None
        self._otf_supplement: int = 0

    # ---- getters (upstream public) ----

    def get_error(self) -> str | None:
        return self._error

    def get_name(self) -> str | None:
        return self._name

    def get_header_mac_style(self) -> int | None:
        """Return ``head.macStyle``, or ``None`` if no ``head`` table."""
        return self._header_mac_style

    def get_os2_windows(self) -> OS2WindowsMetricsTable | None:
        return self._os2_windows

    def get_font_family(self) -> str | None:
        return self._font_family

    def get_font_sub_family(self) -> str | None:
        return self._font_sub_family

    def is_open_type_post_script(self) -> bool:
        return self._is_otf_and_post_script

    def get_non_otf_table_gcid_142(self) -> bytes | None:
        return self._non_otf_gcid_142

    def get_otf_registry(self) -> str | None:
        return self._otf_registry

    def get_otf_ordering(self) -> str | None:
        return self._otf_ordering

    def get_otf_supplement(self) -> int:
        return self._otf_supplement

    # ---- setters (upstream package-private + public setError/setOtfROS) ----

    def set_error(self, exception: str) -> None:
        self._error = exception

    def set_name(self, name: str | None) -> None:
        self._name = name

    def set_header_mac_style(self, header_mac_style: int | None) -> None:
        self._header_mac_style = header_mac_style

    def set_os2_windows(self, os2_windows: OS2WindowsMetricsTable | None) -> None:
        self._os2_windows = os2_windows

    def set_font_family(
        self,
        font_family: str | None,
        font_sub_family: str | None,
    ) -> None:
        self._font_family = font_family
        self._font_sub_family = font_sub_family

    def set_non_otf_gcid_142(self, value: bytes | None) -> None:
        self._non_otf_gcid_142 = value

    def set_is_otf_and_post_script(self, value: bool) -> None:  # noqa: FBT001
        self._is_otf_and_post_script = value

    def set_otf_ros(
        self,
        otf_registry: str | None,
        otf_ordering: str | None,
        otf_supplement: int,
    ) -> None:
        """Mirror upstream ``setOtfROS`` (public so a CFF parser in a
        sibling package can populate ROS data)."""
        self._otf_registry = otf_registry
        self._otf_ordering = otf_ordering
        self._otf_supplement = otf_supplement


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

    # ---------- table-header fast path --------------------------------
    # Mirrors upstream ``parseTableHeaders(RandomAccessRead)`` /
    # ``parseTableHeaders(TTFDataStream)`` (TTFParser.java L114-L324).
    # PDFBox's ``FileSystemFontProvider.scanFonts(...)`` calls this to
    # collect just the metadata needed to decide whether a font on disk
    # is interesting, without paying for full table decode.

    def parse_table_headers(
        self,
        source: bytes
        | bytearray
        | memoryview
        | str
        | os.PathLike[str]
        | BinaryIO
        | TTFDataStream
        | RandomAccessRead,
    ) -> FontHeaders:
        """Parse only the headers needed for font enumeration.

        Returns a populated :class:`FontHeaders`. On non-fatal validation
        failure (e.g. CFF in a TTF, missing mandatory table) the returned
        instance carries the failure on :meth:`FontHeaders.get_error`
        rather than raising, matching upstream's
        ``outHeaders.setError(...); return outHeaders`` semantics.
        """
        stream = self._coerce_to_data_stream(source)
        return self._parse_table_headers_from_stream(stream)

    def _parse_table_headers_from_stream(
        self,
        data: TTFDataStream,
    ) -> FontHeaders:
        out = FontHeaders()

        # We have no streaming SFNT directory walker — fontTools has
        # already loaded the whole font when we hand the stream off via
        # ``_new_font``. This is fine for the fast-path: we just probe
        # the resulting font for the same fields upstream's loop fills in.
        try:
            raw = data.get_original_data()
        except Exception as exc:  # noqa: BLE001 — surface as FontHeaders error
            out.set_error(f"could not read SFNT bytes: {exc}")
            return out

        if len(raw) < 4:
            out.set_error(f"SFNT stream too short: {len(raw)} bytes")
            return out

        scaler = int.from_bytes(raw[:4], "big", signed=False)
        if scaler == _TAG_OPEN_TYPE_CFF and not self._allow_cff():
            out.set_error("True Type fonts using CFF outlines are not supported")
            return out
        if scaler not in (
            _TAG_TRUE_TYPE,
            _TAG_TRUE,
            _TAG_TYP1,
            _TAG_OPEN_TYPE_CFF,
        ):
            out.set_error(f"unsupported SFNT scaler type: 0x{scaler:08X}")
            return out

        try:
            font = self._new_font(data)
        except Exception as exc:  # noqa: BLE001
            out.set_error(f"could not load font: {exc}")
            return out

        # name + family/sub-family from the 'name' table
        naming = font.get_naming() if hasattr(font, "get_naming") else None
        if naming is not None:
            try:
                out.set_name(naming.get_post_script_name())
            except (AttributeError, ValueError, OSError):
                out.set_name(None)
            try:
                family = naming.get_font_family()
                sub_family = naming.get_font_sub_family()
                out.set_font_family(family, sub_family)
            except (AttributeError, ValueError, OSError):
                pass

        # macStyle from the 'head' table (None when absent — upstream's
        # FontHeaders.getHeaderMacStyle() doc explicitly defines that).
        header = font.get_header() if hasattr(font, "get_header") else None
        if header is not None:
            with contextlib.suppress(AttributeError):
                out.set_header_mac_style(header.get_mac_style())

        # OS/2 (used for sFamilyClass / weight / panose / codepage range)
        if hasattr(font, "get_os2_windows"):
            with contextlib.suppress(AttributeError, ValueError, OSError):
                out.set_os2_windows(font.get_os2_windows())

        # OTF + isPostScript discrimination
        from .open_type_font import OpenTypeFont  # noqa: PLC0415

        is_otf_and_post_script = False
        if isinstance(font, OpenTypeFont):
            try:
                is_otf_and_post_script = bool(font.is_post_script())
            except AttributeError:
                is_otf_and_post_script = False
        elif font.has_table("CFF "):
            out.set_error("True Type fonts using CFF outlines are not supported")
            return out
        out.set_is_otf_and_post_script(is_otf_and_post_script)

        # Mandatory-tables presence — list mirrors upstream L302-L312.
        mandatory_tables = [
            "head",
            "hhea",
            "maxp",
            None if self._is_embedded else "post",
            None if is_otf_and_post_script else "loca",
            None if is_otf_and_post_script else "glyf",
            None if self._is_embedded else "name",
            "hmtx",
            None if self._is_embedded else "cmap",
        ]
        for tag in mandatory_tables:
            if tag is not None and not font.has_table(tag):
                out.set_error(f"'{tag}' table is mandatory")
                return out

        return out

    # ---------- factory hook for OTF subclass --------------------------

    def _new_font(self, data: TTFDataStream) -> TrueTypeFont:
        """Produce the concrete font instance.

        Overridden by :class:`OTFParser` to return :class:`OpenTypeFont`.
        """
        return TrueTypeFont(data)

    def _read_table(self, tag: str) -> TTFTable:  # noqa: ARG002 — tag kept for parity
        """Factory hook for unknown tables encountered in the SFNT
        directory.

        Mirrors upstream ``TTFParser.readTable(String)`` (protected,
        TTFParser.java L403-L407): when a tag does not match any of the
        well-known cases in ``readTableDirectory``, upstream calls this
        to produce a generic :class:`TTFTable`. Subclasses can override
        to return a specialised table type for tags they care about.
        """
        return TTFTable()

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


__all__ = ["FontHeaders", "TTFParser"]
