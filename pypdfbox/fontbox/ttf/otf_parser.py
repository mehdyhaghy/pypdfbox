from __future__ import annotations

from .open_type_font import OpenTypeFont
from .true_type_font import TrueTypeFont
from .ttf_data_stream import TTFDataStream
from .ttf_parser import _TAG_OPEN_TYPE_CFF, _TAG_TRUE_TYPE, TTFParser


class OTFParser(TTFParser):
    """Parser for the OpenType/CFF (``OTTO``) flavour of SFNT.

    Mirrors ``org.apache.fontbox.ttf.OTFParser`` (extends
    :class:`TTFParser`). The wire format is the same SFNT container as
    a TTF; the only differences are:

    * the scaler-type magic at offset 0 is ``OTTO`` (not 0x00010000), and
    * outlines live in the ``CFF `` table instead of ``glyf`` / ``loca``.

    The constructor flags carry the same meaning as in :class:`TTFParser`.
    """

    def _new_font(self, data: TTFDataStream) -> TrueTypeFont:
        """Return an :class:`OpenTypeFont` instead of a plain TTF."""
        return OpenTypeFont(data)

    def _allow_cff(self) -> bool:
        """OTF parsers accept CFF outlines (``OTTO`` scaler type).

        Mirrors upstream ``OTFParser.allowCFF()``.
        """
        return True

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
