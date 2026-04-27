from __future__ import annotations

from typing import Any

from .cff_font import CFFFont


class CFFType1Font(CFFFont):
    """Name-keyed (Type 1-flavoured) Compact Font Format font.

    Mirrors upstream ``org.apache.fontbox.cff.CFFType1Font`` (which
    extends ``CFFFont``). A Type 1-flavoured CFF carries:

    * A name-keyed /CharStrings INDEX (no /ROS, no /FDSelect, no
      /FDArray).
    * A single Top-level /Private DICT.
    * An /Encoding (Standard, Expert, or a custom array of GID→code
      mappings) selecting which glyphs are reachable from a 1-byte
      character code.

    Parsing stays in :class:`CFFFont`; this subclass only adds Type
    1-specific accessors. Construct via :meth:`from_bytes` or
    :meth:`from_cff_font`.
    """

    # ---------- factories ----------

    @classmethod
    def from_bytes(cls, data: bytes | bytearray | memoryview) -> "CFFType1Font":
        """Parse a CFF byte stream as a name-keyed (Type 1) font.

        Raises ``OSError`` when the parsed font is CIDKeyed (i.e. has
        a /ROS Top DICT entry). Use :meth:`CFFFont.from_bytes` for
        permissive parsing.
        """
        base = CFFFont.from_bytes(data)
        if base.is_cid_font():
            msg = "CFF font is CIDKeyed, not name-keyed; use CFFCIDFont"
            raise OSError(msg)
        return cls.from_cff_font(base)

    @classmethod
    def from_cff_font(cls, base: CFFFont) -> "CFFType1Font":
        """Re-wrap an already-parsed :class:`CFFFont` as a
        :class:`CFFType1Font`. Cheap — shares the underlying fontTools
        font set, no re-decompilation."""
        instance = cls()
        instance._fontset = base._fontset  # noqa: SLF001
        instance._top = base._top  # noqa: SLF001
        return instance

    # ---------- encoding ----------

    def get_encoding(self) -> Any:
        """The CFF /Encoding for this font.

        fontTools surfaces this either as the string ``"StandardEncoding"``
        / ``"ExpertEncoding"`` (predefined encodings 0/1) or as a list of
        glyph-name-to-code mappings for a custom encoding. We pass it
        through as-is so callers can branch on type — this matches the
        PDFBox contract where ``getEncoding()`` returns a polymorphic
        ``CFFEncoding`` (subclassed by predefined / custom).

        Returns ``None`` when no /Encoding is present (the CFF default
        is StandardEncoding, but a missing attribute is reported as
        ``None`` to let callers detect the absence explicitly).
        """
        if self._top is None:
            return None
        return getattr(self._top, "Encoding", None)

    def is_standard_encoding(self) -> bool:
        """True when the font uses the predefined StandardEncoding."""
        return self.get_encoding() == "StandardEncoding"

    def is_expert_encoding(self) -> bool:
        """True when the font uses the predefined ExpertEncoding."""
        return self.get_encoding() == "ExpertEncoding"

    def is_custom_encoding(self) -> bool:
        """True when the font carries a custom (non-predefined) encoding
        array, i.e. /Encoding is not a string."""
        enc = self.get_encoding()
        return enc is not None and not isinstance(enc, str)

    # ---------- name → GID ----------

    def name_to_gid(self, name: str) -> int:
        """Resolve a glyph name to its GID via the charset.

        Returns 0 (.notdef) for an unmapped name — matches the PDF
        rendering contract for missing glyphs. Linear scan; cache
        externally for hot paths.
        """
        if not name:
            return 0
        for gid, candidate in enumerate(self.get_charset()):
            if candidate == name:
                return gid
        return 0

    def code_to_name(self, code: int) -> str:
        """Resolve a 1-byte character code to a glyph name via the
        font's /Encoding.

        Returns ``".notdef"`` for unmapped codes or when the font has no
        encoding. Predefined encodings (Standard/Expert) are not
        materialised by us — fontTools normalises these to the string
        name and we return ``".notdef"`` for them, matching the
        upstream behaviour of letting the caller resolve via the
        canonical encoding tables externally.
        """
        if not 0 <= code <= 255:
            return ".notdef"
        enc = self.get_encoding()
        if enc is None or isinstance(enc, str):
            # Predefined encoding — caller must consult an external
            # StandardEncoding / ExpertEncoding table.
            return ".notdef"
        try:
            name = enc[code]
        except (IndexError, KeyError, TypeError):
            return ".notdef"
        return str(name) if name else ".notdef"

    def is_cid_font(self) -> bool:  # noqa: D401 — overrides base
        """A :class:`CFFType1Font` is name-keyed, never CIDKeyed."""
        return False


__all__ = ["CFFType1Font"]
