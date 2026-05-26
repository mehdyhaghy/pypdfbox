from __future__ import annotations

from collections.abc import Mapping

from .encoding import Encoding


class BuiltInEncoding(Encoding):
    """A font's built-in encoding. This is a custom encoding embedded in a font.

    Mirrors ``org.apache.fontbox.encoding.BuiltInEncoding``. This is the
    fontbox-level built-in encoding (distinct from the richer
    ``pypdfbox.pdmodel.font.encoding.BuiltInEncoding``): it is produced by the
    Type 1 parser when a font carries an inline ``Encoding`` array of
    ``dup <code> /<glyph> put`` pairs rather than a named predefined encoding.

    The instance is constructed from a ``code -> glyph name`` mapping. Upstream
    populates it via ``codeToName.forEach(this::addCharacterEncoding)`` and adds
    no further behaviour over the abstract :class:`Encoding` base.
    """

    def __init__(self, code_to_name: Mapping[int, str]) -> None:
        super().__init__()
        # Upstream: ``codeToName.forEach(this::addCharacterEncoding)``.
        # ``add_character_encoding`` delegates to ``add``, which keeps the
        # first reverse mapping for a glyph name (Java ``Map.putIfAbsent``
        # semantics). Accept any ``Mapping`` for parity with Java's
        # ``Map<Integer, String>`` interface.
        for code, name in code_to_name.items():
            self.add_character_encoding(code, name)


__all__ = ["BuiltInEncoding"]
