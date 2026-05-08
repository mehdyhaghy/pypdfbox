"""Encoding-to-glyph mapping rows produced by ``Type1Font.get_type1_mappings``.

Mirrors :class:`org.apache.fontbox.type1.Type1Mapping` from upstream
PDFBox — a small immutable triple of ``(code, glyph_name, char_string)``.
Upstream uses Java getter methods (``getCode`` / ``getName`` /
``getType1CharString``); we mirror those as ``get_code`` /
``get_name`` / ``get_type1_char_string`` and also expose them as
properties so the value reads naturally in Python (``mapping.code``).
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any


class Type1Mapping:
    """One ``(code -> glyph)`` row of a Type 1 encoding vector.

    Equivalent to upstream's static inner class
    ``Type1Font.Type1Mapping``. Instances are immutable value objects;
    equality is structural across the three fields so callers can use
    them as dict keys or compare encoding vectors directly.
    """

    __slots__ = ("_code", "_name", "_char_string")

    def __init__(
        self,
        code: int,
        name: str,
        char_string: Any | None,
    ) -> None:
        self._code = int(code)
        self._name = str(name)
        self._char_string = char_string

    # ---------- upstream-compatible getters ----------

    def get_code(self) -> int:
        """Encoding slot (0-255 for single-byte Type 1 encodings)."""
        return self._code

    def get_name(self) -> str:
        """PostScript glyph name (e.g. ``A``, ``ampersand``, ``.notdef``)."""
        return self._name

    def get_type1_char_string(self) -> Any | None:
        """Wrapped charstring for this glyph. ``None`` when the encoding
        slot points at a glyph the font does not actually define."""
        return self._char_string

    # ---------- pythonic conveniences ----------

    @property
    def code(self) -> int:
        return self._code

    @property
    def name(self) -> str:
        return self._name

    @property
    def char_string(self) -> Any | None:
        return self._char_string

    # ---------- tuple-style unpacking ----------

    def as_tuple(self) -> tuple[int, str, Any | None]:
        """Return the row as a ``(code, name, char_string)`` tuple.

        Convenient for assertions and when serialising encoding vectors
        for diff'ing against upstream output.
        """
        return (self._code, self._name, self._char_string)

    def __iter__(self) -> Iterator[Any]:
        """Iterate ``(code, name, char_string)`` so callers can write
        ``code, name, cs = mapping`` the same way they would for a
        ``namedtuple``."""
        yield self._code
        yield self._name
        yield self._char_string

    def with_char_string(
        self, char_string: Any | None
    ) -> Type1Mapping:
        """Return a copy with ``char_string`` replaced.

        Type1Mapping is immutable; this is the canonical way to swap in
        a re-parsed charstring (e.g. after lazy decryption) without
        mutating the original row.
        """
        return Type1Mapping(self._code, self._name, char_string)

    # ---------- value semantics ----------

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Type1Mapping):
            return NotImplemented
        return (
            self._code == other._code
            and self._name == other._name
            and self._char_string is other._char_string
        )

    def __hash__(self) -> int:
        # Charstrings may be unhashable; key off identity so Type1Mapping
        # itself stays hashable for set / dict use.
        cs_id: Any = id(self._char_string) if self._char_string is not None else None
        return hash((self._code, self._name, cs_id))

    def __repr__(self) -> str:
        return (
            f"Type1Mapping(code={self._code}, name={self._name!r}, "
            f"char_string={self._char_string!r})"
        )


__all__ = ["Type1Mapping"]
