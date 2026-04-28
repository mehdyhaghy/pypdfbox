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

        Returns ``".notdef"`` for unmapped codes or when the font has
        no encoding. Predefined encodings (Standard/Expert) are
        resolved through the canonical Adobe tables — Standard via
        :class:`pypdfbox.fontbox.encoding.standard_encoding.StandardEncoding`
        (Adobe Standard, used by CFF EncodingId 0) and Expert via the
        font's parsed encoding when available.
        """
        if not 0 <= code <= 255:
            return ".notdef"
        enc = self.get_encoding()
        if enc is None:
            return ".notdef"
        if isinstance(enc, str):
            if enc == "StandardEncoding":
                from pypdfbox.fontbox.encoding.standard_encoding import (  # noqa: PLC0415
                    StandardEncoding,
                )

                return StandardEncoding.INSTANCE.get_name(code)
            if enc == "ExpertEncoding":
                # Expert isn't part of our pdmodel encoding cluster; fall
                # back to the per-GID charset where the predefined
                # encoding's SIDs have already been resolved by fontTools.
                return self._expert_code_to_name(code)
            return ".notdef"
        try:
            name = enc[code]
        except (IndexError, KeyError, TypeError):
            return ".notdef"
        return str(name) if name else ".notdef"

    @staticmethod
    def _expert_code_to_name(code: int) -> str:
        """Look up a code in the CFF Expert encoding (Adobe Technote
        #5176, Appendix B). Returns ``".notdef"`` for unmapped codes.

        fontTools doesn't expose the Expert encoding's code-to-SID
        table via public API; we resolve via the static table built
        in :mod:`pypdfbox.fontbox.cff._expert_encoding`.
        """
        from pypdfbox.fontbox.cff._expert_encoding import (  # noqa: PLC0415
            EXPERT_ENCODING_TABLE,
        )

        return EXPERT_ENCODING_TABLE.get(code, ".notdef")

    def name_to_code(self, name: str) -> int:
        """Resolve a glyph name to its 1-byte code via the font's
        /Encoding. Returns ``-1`` for unmapped names."""
        if not name:
            return -1
        enc = self.get_encoding()
        if enc is None:
            return -1
        if isinstance(enc, str):
            if enc == "StandardEncoding":
                from pypdfbox.fontbox.encoding.standard_encoding import (  # noqa: PLC0415
                    StandardEncoding,
                )

                code = StandardEncoding.INSTANCE.get_code(name)
                return -1 if code is None else int(code)
            if enc == "ExpertEncoding":
                from pypdfbox.fontbox.cff._expert_encoding import (  # noqa: PLC0415
                    EXPERT_ENCODING_TABLE,
                )

                for code, candidate in EXPERT_ENCODING_TABLE.items():
                    if candidate == name:
                        return code
            return -1
        # Custom encoding — list-shaped table mapping code → name.
        try:
            for i, candidate in enumerate(enc):
                if candidate == name:
                    return i
        except TypeError:
            return -1
        return -1

    # ---------- glyph access (parity helpers) ----------

    def has_glyph(self, name: str) -> bool:  # noqa: D401 — overrides base
        """PDFBox: ``CFFType1Font.hasGlyph(String)`` — true when the
        charset contains ``name``. Inherited base class checks the
        CharStrings index by name; both views agree for name-keyed CFF.
        """
        if not name:
            return False
        return name in self.get_charset() or super().has_glyph(name)

    def get_path(self, name: str) -> list[tuple]:  # noqa: D401 — overrides base
        """PDFBox: ``CFFType1Font.getPath(String)`` — name-keyed glyph
        path. Mirrors the inherited GID-keyed
        :meth:`CFFFont.get_path` but takes a PostScript name."""
        return super().get_path(name)

    def get_width(self, name: str) -> float:  # noqa: D401 — overrides base
        """PDFBox: ``CFFType1Font.getWidth(String)`` — name-keyed
        advance width."""
        return super().get_width(name)

    def get_type1_char_string(self, name: str) -> Any:
        """PDFBox: ``CFFType1Font.getType1CharString(String)`` — return
        the Type 1 charstring wrapper for ``name``. Falls back to the
        ``.notdef`` glyph when the name is unknown.

        Note: under the hood CFF uses Type 2 charstrings, not Type 1 —
        upstream's method name is a historical artefact. The returned
        wrapper is therefore a :class:`Type2CharString` (which is what
        actually matches the on-disk encoding); this matches the
        behaviour of ``CFFType1Font`` whose ``getType2CharString(int)``
        is the canonical accessor.
        """
        gid = self.name_to_gid(name)
        return self.get_type2_char_string(gid)

    def is_cid_font(self) -> bool:  # noqa: D401 — overrides base
        """A :class:`CFFType1Font` is name-keyed, never CIDKeyed."""
        return False


__all__ = ["CFFType1Font"]
