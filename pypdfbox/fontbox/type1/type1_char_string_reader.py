"""Interface for objects that can resolve a glyph name to a Type 1 CharString.

Mirrors ``org.apache.fontbox.type1.Type1CharStringReader`` (PDFBox 3.0,
``fontbox/src/main/java/org/apache/fontbox/type1/Type1CharStringReader.java``).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pypdfbox.fontbox.cff.type1_char_string import Type1CharString


class Type1CharStringReader(ABC):
    """Implementers can look up a CharString by glyph name."""

    @abstractmethod
    def get_type1_char_string(self, name: str) -> Type1CharString:
        """Return the Type 1 CharString for glyph ``name``.

        Raises :class:`OSError` if the lookup fails.
        """


__all__ = ["Type1CharStringReader"]
