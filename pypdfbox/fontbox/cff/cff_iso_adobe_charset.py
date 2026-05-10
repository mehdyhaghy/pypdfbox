"""Singleton :class:`CFFISOAdobeCharset`.

Ported from ``org.apache.fontbox.cff.CFFISOAdobeCharset``
(``fontbox/src/main/java/org/apache/fontbox/cff/CFFISOAdobeCharset.java``
lines 25-282).

The 229-entry SID/name table is supplied by fontTools
(``cffISOAdobeStrings``) instead of being transcribed by hand; the table
is identical to upstream's ``cffIsoAdobeCharsetTable`` and to the CFF
spec's predefined ISOAdobe charset (where SID == GID for the first 229
glyphs).
"""

from __future__ import annotations

from fontTools.cffLib import cffISOAdobeStrings

from .cff_charset_type1 import CFFCharsetType1


class CFFISOAdobeCharset(CFFCharsetType1):
    """ISO Adobe charset, used when ``CharsetId`` is 0."""

    _instance: CFFISOAdobeCharset | None = None

    def __init__(self) -> None:
        super().__init__()
        # Upstream lines 264-268: gid increments while sid is read from the
        # table. ISOAdobe is a predefined charset where GID == SID for the
        # 229 glyphs, so we can iterate ``cffISOAdobeStrings`` directly.
        for gid, name in enumerate(cffISOAdobeStrings):
            self.add_sid(gid, gid, name)

    @classmethod
    def get_instance(cls) -> CFFISOAdobeCharset:
        """Return the shared singleton instance (upstream
        ``CFFISOAdobeCharset.getInstance()``, lines 275-280)."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
