"""Private Type 1 char-string reader interface.

Mirrors upstream's pattern of inner-class
``PrivateType1CharStringReader`` (CFFCIDFont.java) implementing the
package-public ``Type1CharStringReader`` interface
(Type1CharStringReader.java:28). The interface defines a single method
returning a ``Type1CharString`` for a given character name — used by the
``seac`` accented-character composite to resolve base / accent glyphs.

Upstream ``CFFCIDFont`` exposes this as a *private inner class* to keep
the lookup hidden behind a non-public surface ("CIDFonts only support
this for legacy 'seac' commands" — CFFCIDFont.java comment). We model
the same shape: a thin abstract base class plus a default
implementation that delegates to a CFF font's ``get_type2_char_string``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .type1_char_string import Type1CharString


class PrivateType1CharStringReader(ABC):
    """Mirrors the upstream inner class
    ``CFFCIDFont.PrivateType1CharStringReader`` and its parent interface
    ``org.apache.fontbox.type1.Type1CharStringReader``
    (Type1CharStringReader.java:28).

    The single method ``get_type1_char_string`` resolves a glyph by name
    — used during ``seac`` composite glyph rendering. Upstream's CID
    variant always returns the ``.notdef`` glyph (gid 0) regardless of
    the requested name; concrete subclasses override to support real
    Type 1 lookup.
    """

    @abstractmethod
    def get_type1_char_string(self, name: str) -> Type1CharString:
        """Mirrors upstream
        ``Type1CharStringReader.getType1CharString(String)``
        (Type1CharStringReader.java:37)."""


class _CFFCIDDefaultReader(PrivateType1CharStringReader):
    """Default ``PrivateType1CharStringReader`` for CID-keyed CFF fonts.

    Mirrors the inner class body from CFFCIDFont.java: regardless of the
    requested glyph name, returns ``getType2CharString(0)`` — i.e. the
    ``.notdef`` Type 1 char string.
    """

    def __init__(self, font: Any) -> None:
        self._font = font

    def get_type1_char_string(self, name: str) -> Type1CharString:  # noqa: ARG002
        return self._font.get_type2_char_string(0)


__all__ = ["PrivateType1CharStringReader"]
