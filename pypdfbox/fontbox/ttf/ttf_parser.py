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
        if scaler == _TAG_OPEN_TYPE_CFF and not self.allow_cff():
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
            font = self.new_font(data)
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

    # ---------- factory hooks (mirror upstream package-private hooks) ----

    def new_font(self, data: TTFDataStream) -> TrueTypeFont:
        """Produce the concrete font instance.

        Mirrors upstream ``TrueTypeFont newFont(TTFDataStream)``
        (TTFParser.java L169-L172). Overridden by :class:`OTFParser`
        to return :class:`OpenTypeFont`.
        """
        return TrueTypeFont(data)

    def read_table(self, tag: str) -> TTFTable:  # noqa: ARG002 — tag kept for parity
        """Factory hook for unknown tables encountered in the SFNT
        directory.

        Mirrors upstream ``protected TTFTable readTable(String)``
        (TTFParser.java L403-L407): when a tag does not match any of
        the well-known cases in ``readTableDirectory``, upstream calls
        this to produce a generic :class:`TTFTable`. Subclasses can
        override to return a specialised table type for tags they
        care about.
        """
        return TTFTable()

    def allow_cff(self) -> bool:
        """Whether CFF outlines (an ``OTTO``-flavoured SFNT) are
        acceptable inputs to this parser.

        Mirrors upstream ``protected boolean allowCFF()``
        (TTFParser.java L326-L329). The base ``TTFParser`` rejects
        CFF; the :class:`OTFParser` subclass overrides this to
        return ``True``.
        """
        return False

    # ---------- legacy underscored aliases -----------------------------
    # Earlier waves shipped these helpers as ``_new_font`` / ``_read_table``
    # / ``_allow_cff``. The public names above are the parity-canonical
    # spellings; the underscored variants forward so any in-repo callers
    # that already imported them keep working without churn.

    def _new_font(self, data: TTFDataStream) -> TrueTypeFont:
        return self.new_font(data)

    def _read_table(self, tag: str) -> TTFTable:
        return self.read_table(tag)

    def _allow_cff(self) -> bool:
        return self.allow_cff()

    # ---------- create_font_with_tables / parse_tables / read_table_directory ----
    # Upstream exposes three internal helpers wired together by ``parse``:
    #
    # * ``createFontWithTables(TTFDataStream)`` (TTFParser.java L130-L160)
    #   — walks the SFNT directory, builds a fresh ``TrueTypeFont``, and
    #   registers each directory entry on it.
    # * ``readTableDirectory(TTFDataStream)`` (TTFParser.java L331-L401)
    #   — reads one 16-byte directory entry and returns the right
    #   :class:`TTFTable` subclass for the tag.
    # * ``parseTables(TrueTypeFont)`` (TTFParser.java L180-L249) —
    #   forces every directory entry to load and validates the
    #   mandatory-tables presence.
    #
    # The fontTools backend already does the directory walk + per-table
    # decode internally when :class:`TrueTypeFont` constructs its
    # underlying ``TTFont``, so these methods become thin wrappers over
    # the resulting ``TrueTypeFont`` (driven by ``get_table_map``). Behaviour
    # observable to PDFBox-shaped callers is preserved.

    def create_font_with_tables(self, raf: TTFDataStream) -> TrueTypeFont:
        """Build a :class:`TrueTypeFont` and register every directory entry.

        Mirrors upstream ``TrueTypeFont createFontWithTables(TTFDataStream)``
        (TTFParser.java L130-L160). The fontTools backend has already
        decoded the SFNT directory by the time :meth:`new_font` returns,
        so this method projects the resulting ``reader.tables`` map back
        into typed :class:`TTFTable` entries via :meth:`read_table_directory`
        and registers them on the font.
        """
        font = self.new_font(raf)
        # SFNT scaler-type fixed-point version (1.0 for TrueType, the
        # ``OTTO``/``true``/``typ1`` floats for legacy magics). Upstream
        # reads it from the stream after newFont(); we already know the
        # 32-bit scaler from the magic check, so encode it as a fixed.
        raw = raf.get_original_data()
        if len(raw) >= 4:
            scaler = int.from_bytes(raw[:4], "big", signed=False)
            # 16.16 fixed → float.
            font.set_version(((scaler >> 16) & 0xFFFF) + (scaler & 0xFFFF) / 65536.0)
        # Walk fontTools' SFNTReader and project each entry back through
        # ``read_table_directory`` so subclass overrides of
        # :meth:`read_table` see every tag, just like the upstream loop.
        reader = getattr(font, "_tt", None)
        reader = getattr(reader, "reader", None) if reader is not None else None
        if reader is None:
            return font
        for tag in reader.tables:
            entry = reader.tables[tag]
            table = self._build_directory_entry(
                tag,
                int(entry.checkSum),
                int(entry.offset),
                int(entry.length),
            )
            if table is None:
                continue
            # Upstream PDFBox-5285 guard: skip tables whose offset+length
            # walks past the file size.
            if table.get_offset() + table.get_length() > font.get_original_data_size():
                continue
            font.add_table(table)
        return font

    def read_table_directory(self, raf: TTFDataStream) -> TTFTable | None:
        """Read one 16-byte SFNT directory entry from ``raf``.

        Mirrors upstream ``TTFTable readTableDirectory(TTFDataStream)``
        (TTFParser.java L331-L401). Each entry is a fixed-layout record:
        4-byte tag + 4-byte checksum + 4-byte offset + 4-byte length.
        Returns ``None`` for zero-length tables (except ``glyf``), per
        upstream's L394-L398 guard.
        """
        tag = raf.read_string(4)
        check_sum = raf.read_unsigned_int()
        offset = raf.read_unsigned_int()
        length = raf.read_unsigned_int()
        return self._build_directory_entry(tag, check_sum, offset, length)

    def _build_directory_entry(
        self,
        tag: str,
        check_sum: int,
        offset: int,
        length: int,
    ) -> TTFTable | None:
        """Shared back-end for :meth:`read_table_directory` and
        :meth:`create_font_with_tables`.

        Resolves the tag through :meth:`read_table` so subclass
        overrides (e.g. :class:`OTFParser`) see every tag, then
        applies the zero-length guard from upstream L394-L398.
        """
        table = self.read_table(tag)
        table.set_tag(tag)
        table.set_check_sum(check_sum)
        table.set_offset(offset)
        table.set_length(length)
        # Upstream skips zero-length tables except ``glyf`` (which is
        # legal at length 0 for all-empty fonts).
        if length == 0 and tag != "glyf":
            return None
        return table

    def parse_tables(self, font: TrueTypeFont) -> None:
        """Force every directory entry to load and validate presence.

        Mirrors upstream ``void parseTables(TrueTypeFont)``
        (TTFParser.java L180-L249). The fontTools backend has already
        decoded the recognised tables by this point, so the per-table
        load amounts to flipping the ``initialized`` flag; the bulk of
        this method is the mandatory-tables check, which mirrors
        :meth:`_check_tables` for the TTF case (and :class:`OTFParser`
        layers the OTF/CFF rule on top via super().parse_tables).
        """
        for table in font.get_tables():
            if not table.get_initialized():
                font.read_table(table)
        self._check_tables(font)

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
        return self.new_font(data)

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
