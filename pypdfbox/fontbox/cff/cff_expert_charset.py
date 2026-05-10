"""Singleton :class:`CFFExpertCharset`.

Ported from ``org.apache.fontbox.cff.CFFExpertCharset``
(``fontbox/src/main/java/org/apache/fontbox/cff/CFFExpertCharset.java``
lines 24-219).

The 166-entry table is provided by fontTools
(``cffIExpertStrings`` + ``cffStandardStringMapping``) instead of being
transcribed by hand. The (SID, name) pairs match upstream's
``cffExpertCharsetTable`` and the CFF spec's predefined Expert charset.
"""

from __future__ import annotations

from fontTools.cffLib import cffIExpertStrings, cffStandardStringMapping

from .cff_charset_type1 import CFFCharsetType1


class CFFExpertCharset(CFFCharsetType1):
    """Adobe Expert charset, used when ``CharsetId`` is 1."""

    _instance: CFFExpertCharset | None = None

    def __init__(self) -> None:
        super().__init__()
        # Upstream lines 201-205: iterate the table assigning sequential
        # GIDs while pulling SID/name from each row. fontTools'
        # ``cffIExpertStrings`` is the same name list in the same order;
        # ``cffStandardStringMapping`` resolves each name to its standard
        # SID (e.g. exclamsmall -> 229, comma -> 13).
        for gid, name in enumerate(cffIExpertStrings):
            sid = cffStandardStringMapping[name]
            self.add_sid(gid, sid, name)

    @classmethod
    def get_instance(cls) -> CFFExpertCharset:
        """Return the shared singleton instance (upstream
        ``CFFExpertCharset.getInstance()``, lines 212-217)."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
