"""Singleton :class:`CFFExpertSubsetCharset`.

Ported from ``org.apache.fontbox.cff.CFFExpertSubsetCharset``
(``fontbox/src/main/java/org/apache/fontbox/cff/CFFExpertSubsetCharset.java``
lines 25-141).

The 87-entry table is supplied by fontTools
(``cffExpertSubsetStrings`` + ``cffStandardStringMapping``).
"""

from __future__ import annotations

from fontTools.cffLib import cffExpertSubsetStrings, cffStandardStringMapping

from .cff_charset_type1 import CFFCharsetType1


class CFFExpertSubsetCharset(CFFCharsetType1):
    """Adobe Expert Subset charset, used when ``CharsetId`` is 2."""

    _instance: CFFExpertSubsetCharset | None = None

    def __init__(self) -> None:
        super().__init__()
        # Upstream lines 123-127: iterate ``cffExpertSubsetCharsetTable``
        # in row order, assigning GID = row index, SID = row[0],
        # name = row[1]. fontTools' ``cffExpertSubsetStrings`` is the
        # same name list; the standard-strings mapping resolves SIDs.
        for gid, name in enumerate(cffExpertSubsetStrings):
            sid = cffStandardStringMapping[name]
            self.add_sid(gid, sid, name)

    @classmethod
    def get_instance(cls) -> CFFExpertSubsetCharset:
        """Return the shared singleton instance (upstream
        ``CFFExpertSubsetCharset.getInstance()``, lines 134-139)."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
