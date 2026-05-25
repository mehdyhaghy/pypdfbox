from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

from pypdfbox.fontbox.cff.byte_source import ByteSource
from pypdfbox.io.random_access_read_buffer import RandomAccessReadBuffer

from .ttf_table import TTFTable

if TYPE_CHECKING:
    from pypdfbox.fontbox.cff.cff_font import CFFFont

    from .true_type_font import TrueTypeFont
    from .ttf_data_stream import TTFDataStream
    from .ttf_parser import FontHeaders


# Upstream CFFTable.TAG (CFFTable.java line 34) — the four-byte SFNT
# table tag identifying the embedded Compact Font Format payload. The
# trailing space is part of the tag itself per the OpenType spec.
_CFF_TABLE_TAG: str = "CFF "


class _CFFByteSource(ByteSource):
    """Default :class:`ByteSource` for re-reading the ``CFF`` table.

    Mirrors the private nested class
    ``org.apache.fontbox.ttf.CFFTable.CFFBytesource`` (``CFFTable.java``
    lines 95-109). PDFBox lets the :class:`CFFParser` re-read the
    payload later by handing it a callback that returns the bytes of
    the host font's ``CFF `` table. We mirror that exact shape so
    subsetting / Type1C fallback paths port across.
    """

    def __init__(self, ttf: TrueTypeFont) -> None:
        self._ttf: TrueTypeFont = ttf

    def get_bytes(self) -> bytes:
        """Re-read the ``CFF `` table bytes from the host font.

        Mirrors ``byte[] getBytes()`` (``CFFTable.java`` lines 104-108):
        looks up the table in the font's table map, then asks the font
        to materialise its bytes.
        """
        table = self._ttf.get_table_map().get(CFFTable.TAG)
        if table is None:
            return b""
        data = self._ttf.get_table_bytes(table)
        return b"" if data is None else bytes(data)


class CFFTable(TTFTable):
    """PostScript font program (Compact Font Format) table inside an SFNT.

    Mirrors ``org.apache.fontbox.ttf.CFFTable`` (``CFFTable.java`` lines
    29-110). The table tag is the four-character ``"CFF "`` (with a
    trailing space) and the payload is an Adobe CFF font program —
    either Type 1 or CID-keyed — which fontTools' :class:`CFFFontSet`
    decompiles via the existing :class:`CFFParser` wrapper.
    """

    # Public tag constant — upstream surfaces this as a ``public static
    # final String`` (``CFFTable.java`` line 34) so callers can refer to
    # the tag by name (e.g. ``ttf.getTableMap().get(CFFTable.TAG)``).
    TAG: str = _CFF_TABLE_TAG

    def __init__(self) -> None:
        super().__init__()
        self._cff_font: CFFFont | None = None

    # ---- read() — full decode --------------------------------------

    def read(self, ttf: TrueTypeFont, data: TTFDataStream) -> None:
        """Parse the ``CFF `` payload off ``data`` into a :class:`CFFFont`.

        Mirrors ``void read(TrueTypeFont ttf, TTFDataStream data)``
        (``CFFTable.java`` lines 50-59). Upstream reads
        ``getLength()`` bytes, hands them to a new :class:`CFFParser`
        with a re-reading :class:`_CFFByteSource`, and keeps the first
        font in the CFF FontSet. Subset-aware Type1C re-parsing later
        re-reads the bytes via the byte source.
        """
        from pypdfbox.fontbox.cff.cff_parser import CFFParser  # noqa: PLC0415

        payload = data.read_bytes(int(self.get_length()))
        parser = CFFParser()
        fonts = parser.parse(payload, _CFFByteSource(ttf))
        # Upstream picks ``.get(0)`` unconditionally; mirror that even
        # though pypdfbox's CFFParser can in theory surface more than
        # one font per CFF NameINDEX entry.
        self._cff_font = fonts[0] if fonts else None
        self.initialized = True

    # ---- read_headers() — fast path for ROS extraction --------------

    def read_headers(
        self,
        ttf: TrueTypeFont,  # noqa: ARG002 — mirror upstream signature
        data: TTFDataStream,
        out_headers: FontHeaders,
    ) -> None:
        """Populate ROS metadata on ``out_headers`` without a full decode.

        Mirrors ``void readHeaders(TrueTypeFont ttf, TTFDataStream
        data, FontHeaders outHeaders)`` (``CFFTable.java`` lines
        61-80). Upstream prefers
        :meth:`TTFDataStream.create_sub_view` so the CFF parser can
        work over the original :class:`RandomAccessRead` without
        slurping the whole table into memory; if no view is available
        we fall back to reading the bytes and wrapping them in a
        :class:`RandomAccessReadBuffer`, matching upstream's same
        fallback path.
        """
        from pypdfbox.fontbox.cff.cff_parser import CFFParser  # noqa: PLC0415

        length = int(self.get_length())
        sub_view = data.create_sub_view(length)
        if sub_view is not None:
            reader = sub_view
            owns_reader = True
        else:
            # ``assert false`` upstream — inefficient because we copy
            # bytes — but we still need to parse them.
            payload = data.read_bytes(length)
            reader = RandomAccessReadBuffer(payload)
            owns_reader = True

        try:
            # ``CFFParser.parse_first_sub_font_ros`` expects either a
            # :class:`ByteSource` or a raw bytes-like; the upstream
            # path hands the :class:`RandomAccessRead` directly. We
            # materialise the bytes here to keep the wrapper's surface
            # narrow (the cost is bounded by the table length anyway).
            buf = bytearray(reader.length())
            reader.seek(0)
            total = 0
            while total < len(buf):
                n = reader.read_into(buf, total, len(buf) - total)
                if n <= 0:  # pragma: no cover - truncated-table safety guard
                    break
                total += n
            CFFParser().parse_first_sub_font_ros(bytes(buf[:total]), out_headers)
        finally:
            # owns_reader is True on both reader-init paths (lines
            # 121/127); the False arc is unreachable defensive code.
            if owns_reader:  # pragma: no cover
                with contextlib.suppress(OSError):
                    reader.close()

    # ---- accessor ---------------------------------------------------

    def get_font(self) -> CFFFont | None:
        """Return the parsed CFF font, or ``None`` if :meth:`read` was
        not called.

        Mirrors ``CFFFont getFont()`` (``CFFTable.java`` lines 87-90).
        Upstream returns the field directly (may be ``null`` until
        ``read`` runs); we mirror that nullable contract.
        """
        return self._cff_font


__all__ = ["CFFTable"]
