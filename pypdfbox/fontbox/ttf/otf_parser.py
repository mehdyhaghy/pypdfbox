from __future__ import annotations

import os
from typing import TYPE_CHECKING, BinaryIO

from .cff_table import CFFTable
from .open_type_font import OpenTypeFont
from .otl_table import OTLTable
from .true_type_font import TrueTypeFont
from .ttf_data_stream import TTFDataStream
from .ttf_parser import _TAG_OPEN_TYPE_CFF, _TAG_TRUE_TYPE, TTFParser
from .ttf_table import TTFTable

if TYPE_CHECKING:
    from pypdfbox.io.random_access_read import RandomAccessRead


# Tags handled by OTFParser.read_table — mirror the upstream switch in
# OTFParser.java L66-L82. CFF and the OpenType Layout (OTL) tags are
# detected here so the directory walker can produce the right placeholder
# table type. fontTools handles the actual decode internally; these tags
# exist to keep the read_table override observable for parity.
_OTF_OTL_TAGS: tuple[str, ...] = ("BASE", "GDEF", "GPOS", "GSUB", "JSTF")
_OTF_CFF_TAG: str = "CFF "


class OTFParser(TTFParser):
    """Parser for the OpenType/CFF (``OTTO``) flavour of SFNT.

    Mirrors ``org.apache.fontbox.ttf.OTFParser`` (extends
    :class:`TTFParser`). The wire format is the same SFNT container as
    a TTF; the only differences are:

    * the scaler-type magic at offset 0 is ``OTTO`` (not 0x00010000), and
    * outlines live in the ``CFF `` table instead of ``glyf`` / ``loca``.

    The constructor flags carry the same meaning as in :class:`TTFParser`.
    """

    # ---------- parse(...) overloads ----------------------------------
    # Upstream OTFParser overrides ``parse`` only to narrow the return
    # type from ``TrueTypeFont`` → ``OpenTypeFont`` (Java covariant
    # return). Python doesn't need that for type-checkers (the value
    # already is an OpenTypeFont via :meth:`new_font`), but the override
    # is preserved on the OTFParser class so parity tooling sees the
    # same surface. Mirrors OTFParser.java L48-L57.

    def parse(  # type: ignore[override]
        self,
        source: bytes
        | bytearray
        | memoryview
        | str
        | os.PathLike[str]
        | BinaryIO
        | TTFDataStream
        | RandomAccessRead,
    ) -> OpenTypeFont:
        """Parse ``source`` and return an :class:`OpenTypeFont`.

        Mirrors ``OpenTypeFont parse(RandomAccessRead)`` /
        ``OpenTypeFont parse(TTFDataStream)`` (OTFParser.java L48, L54).
        Upstream's two Java overloads collapse to one in Python — both
        delegate to ``super().parse`` and downcast to ``OpenTypeFont``.
        """
        font = super().parse(source)
        # ``new_font`` already returned an OpenTypeFont, so this assert
        # documents the invariant rather than coercing.
        assert isinstance(font, OpenTypeFont)
        return font

    # ---------- factory hooks (public on OTFParser, mirroring upstream) ----

    def new_font(self, data: TTFDataStream) -> OpenTypeFont:
        """Produce an :class:`OpenTypeFont` for the given data stream.

        Mirrors ``OpenTypeFont newFont(TTFDataStream)`` (OTFParser.java
        L60-L63). Package-private in Java; exposed as snake_case here so
        the override is observable to PDFBox-shaped callers and parity
        tooling.
        """
        return OpenTypeFont(data)

    def read_table(self, tag: str) -> TTFTable:
        """Resolve a table tag to the right :class:`TTFTable` subclass.

        Mirrors ``TTFTable readTable(String)`` (OTFParser.java L66-L82).
        The upstream switch returns ``OTLTable`` for the OpenType Layout
        tags (``BASE``, ``GDEF``, ``GPOS``, ``GSUB``, ``JSTF``) and
        ``CFFTable`` for ``CFF ``. fontTools handles the per-table decode
        for us, but the placeholders carry the correct type and tag so
        callers that key off the table map (``has_table``, presence
        checks) and PDFBox-shaped callers (``get_tag()`` returns the
        right tag string) behave identically. Note upstream deliberately
        routes ``GSUB`` to ``OTLTable`` too (the ``readTable`` switch is a
        stub); the real GSUB projection comes from
        :meth:`TrueTypeFont.get_gsub`, which reads fontTools directly.
        """
        if tag in _OTF_OTL_TAGS:
            table = OTLTable()
            table._tag = tag  # noqa: SLF001 — mirrors upstream constructor
            return table
        if tag == _OTF_CFF_TAG:
            cff = CFFTable()
            cff._tag = tag  # noqa: SLF001 — mirrors upstream constructor
            return cff
        return super().read_table(tag)

    def allow_cff(self) -> bool:
        """OTF parsers accept CFF outlines (``OTTO`` scaler type).

        Mirrors ``boolean allowCFF()`` (OTFParser.java L85-L88).
        """
        return True

    # ---------- legacy private hooks (kept for back-compat in this repo) ----
    # The leading-underscore variants pre-date the wave that surfaced
    # the public names above. They simply forward; callers in this
    # codebase that already imported them keep working.

    def _new_font(self, data: TTFDataStream) -> TrueTypeFont:
        return self.new_font(data)

    def _allow_cff(self) -> bool:
        return self.allow_cff()

    def _read_table(self, tag: str) -> TTFTable:
        return self.read_table(tag)

    # ---------- scaler-type / table-presence overrides --------------------

    def _check_scaler_type(self, scaler: int) -> None:
        """Accept ``OTTO`` (and tolerate a TrueType-flavoured stream).

        Upstream's OTFParser also tolerates a 0x00010000 (TrueType)
        scaler type — some "OpenType" fonts ship with TrueType outlines
        and rely on the ``OTFParser`` entry point to surface the
        OS/2-derived OpenType-only metadata. We mirror that leniency:
        any TTF-shaped stream parses successfully, just without a
        ``CFF`` payload (``get_cff()`` returns ``None``).
        """
        if scaler in (_TAG_OPEN_TYPE_CFF, _TAG_TRUE_TYPE):
            return
        msg = (
            f"unsupported SFNT scaler type for OTFParser: 0x{scaler:08X} "
            "(expected 'OTTO' or TrueType 0x00010000)"
        )
        raise OSError(msg)

    def _check_tables(self, font: TrueTypeFont) -> None:
        """Mandatory-table presence check for OTF/CFF.

        Same required-table set as TTF, except OTF/CFF replaces
        ``glyf`` with ``CFF`` for outlines. The check on outline tables
        is skipped here because :class:`TTFParser._check_tables` already
        validates the shared core (head/hhea/maxp/hmtx/post/name/cmap).
        For embedded mode we tolerate missing tables (PDF subsets often
        omit them).
        """
        super()._check_tables(font)
        if self._is_embedded:
            return
        if isinstance(font, OpenTypeFont) and not font.is_supported_otf():
            # Lenient: OTFParser also accepts TrueType-flavoured fonts
            # (see :meth:`_check_scaler_type`), so the absence of a CFF
            # table is only an error when the file actually carries the
            # OTTO magic. We checked the magic before constructing the
            # font; reaching this branch with no CFF means upstream-style
            # tolerance applies and we let the caller decide.
            return


__all__ = ["OTFParser"]
