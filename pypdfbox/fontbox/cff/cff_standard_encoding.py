"""CFF Standard Encoding singleton (EncodingId 0).

Mirrors ``org.apache.fontbox.cff.CFFStandardEncoding`` from upstream
PDFBox 3.0. The upstream Java version hardcodes a 256-entry table of
(code, sid) pairs and resolves each SID via ``CFFStandardString``.

**Library-first**: the same Adobe Standard Encoding is shipped with
fontTools as ``fontTools.encodings.StandardEncoding.StandardEncoding``
(a 256-element list of glyph names), which is byte-for-byte equivalent
to the resolved upstream table — verified against the Java samples in
``CFFEncodingTest`` (codes 0/32/112/251). We wrap that list rather than
transcribing 256 SID rows.
"""

from __future__ import annotations

from fontTools.encodings.StandardEncoding import (  # type: ignore[import-untyped]
    StandardEncoding as _FT_STANDARD_ENCODING,
)

from .cff_encoding import CFFEncoding


class CFFStandardEncoding(CFFEncoding):
    """Singleton for the predefined CFF Standard Encoding."""

    _instance: CFFStandardEncoding | None = None

    def __init__(self) -> None:
        super().__init__()
        # Walk fontTools' StandardEncoding list; each index is the char
        # code, each value is the glyph name (or ".notdef" for unmapped
        # slots, exactly matching upstream which would call add(code, 0)
        # for those and resolve SID 0 -> ".notdef").
        # Write directly to the underlying maps so we don't go through
        # CFFEncoding.add (which expects (code, sid[, name]) and would
        # mistype `name` as `sid`). The base Encoding.add semantics are
        # "putIfAbsent" on name->code; replicate that here.
        # pylint: disable=protected-access
        for code, name in enumerate(_FT_STANDARD_ENCODING):
            self._code_to_name[code] = name
            if name not in self._name_to_code:
                self._name_to_code[name] = code

    @classmethod
    def get_instance(cls) -> CFFStandardEncoding:
        """Return the shared singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance


__all__ = ["CFFStandardEncoding"]
