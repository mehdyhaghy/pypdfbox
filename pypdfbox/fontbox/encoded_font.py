"""PostScript-encoded fontbox font protocol.

Mirrors ``org.apache.fontbox.EncodedFont`` from upstream Apache FontBox
3.0. Implementations include :class:`pypdfbox.fontbox.type1.Type1Font`
and :class:`pypdfbox.fontbox.cff.CFFType1Font` — fonts that expose a
PostScript ``Encoding`` vector.

Upstream Java declares this as an ``interface``; we use
``typing.Protocol`` (runtime-checkable) so the existing duck-typed
fontbox classes satisfy ``isinstance(font, EncodedFont)`` without
having to touch their MRO. The single method follows the project
porting rule (camelCase → snake_case):

- ``getEncoding`` → :meth:`get_encoding`
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class EncodedFont(Protocol):
    """Protocol for fontbox fonts that have a PostScript Encoding.

    Java upstream:
        ``public interface EncodedFont`` in
        ``org.apache.fontbox`` (Apache PDFBox 3.0,
        ``fontbox/src/main/java/org/apache/fontbox/EncodedFont.java``).
    """

    def get_encoding(self) -> Any:
        """Return the PostScript ``Encoding`` vector of the font.

        Mirrors upstream ``Encoding getEncoding()``. Concrete fontbox
        encoded fonts return a :class:`pypdfbox.fontbox.encoding.Encoding`
        instance; the protocol intentionally types this as ``Any`` so
        custom encoded fonts that subclass ``Encoding`` (e.g. Type1
        custom encodings) still satisfy the protocol.
        """
        ...


__all__ = ["EncodedFont"]
