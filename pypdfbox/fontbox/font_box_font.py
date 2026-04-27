"""Common interface for all FontBox fonts.

Mirrors ``org.apache.fontbox.FontBoxFont`` from upstream Apache FontBox
3.0. Implementations include :class:`pypdfbox.fontbox.ttf.TrueTypeFont`,
:class:`pypdfbox.fontbox.type1.Type1Font` and
:class:`pypdfbox.fontbox.cff.CFFFont`.

Upstream Java declares this as an ``interface``; we use
``typing.Protocol`` (runtime-checkable) so the existing duck-typed
fontbox classes satisfy ``isinstance(font, FontBoxFont)`` without having
to touch their MRO. The method names are the snake_case rendering of
the upstream Java per the project porting rules:

- ``getName``        → :meth:`get_name`
- ``getFontBBox``    → :meth:`get_font_bbox`
- ``getFontMatrix``  → :meth:`get_font_matrix`
- ``getPath``        → :meth:`get_path`
- ``getWidth``       → :meth:`get_width`
- ``hasGlyph``       → :meth:`has_glyph`

The ``BoundingBox`` return type from upstream ``getFontBBox`` is modeled
as a 4-tuple ``(xmin, ymin, xmax, ymax)`` — the existing fontbox font
classes already return that shape.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class FontBoxFont(Protocol):
    """Protocol satisfied by every FontBox font implementation.

    Java upstream:
        ``public interface FontBoxFont`` in
        ``org.apache.fontbox`` (Apache PDFBox 3.0,
        ``fontbox/src/main/java/org/apache/fontbox/FontBoxFont.java``).

    All accessors raise on read errors; in upstream they raise
    ``IOException``, here :class:`OSError` per the project's Java→Python
    exception mapping.
    """

    def get_name(self) -> str | None:
        """Return the PostScript name of the font (or ``None``).

        Mirrors upstream ``String getName() throws IOException``.
        """
        ...

    def get_font_bbox(self) -> Any:
        """Return the font's bounding box in PostScript units.

        Upstream returns ``BoundingBox``. The existing pypdfbox font
        classes (``TrueTypeFont`` / ``Type1Font`` / ``CFFFont``) return
        a 4-tuple ``(xmin, ymin, xmax, ymax)``; we keep ``Any`` here so
        either shape satisfies the protocol.
        """
        ...

    def get_font_matrix(self) -> list[float]:
        """Return the font matrix in PostScript units.

        Mirrors upstream ``List<Number> getFontMatrix()``. Six floats
        per PostScript convention: ``[sx, 0, 0, sy, tx, ty]`` for most
        fonts (``[0.001, 0, 0, 0.001, 0, 0]`` for typical Type 1).
        """
        ...

    def get_path(self, name: str) -> Any:
        """Return the glyph path for ``name``.

        Mirrors upstream ``GeneralPath getPath(String name)``. Pypdfbox
        doesn't depend on AWT's ``GeneralPath``; concrete fontbox
        classes return a list of path-segment tuples. Typed as ``Any``
        so the protocol accepts either.
        """
        ...

    def get_width(self, name: str) -> float:
        """Return the advance width for the glyph called ``name``.

        Mirrors upstream ``float getWidth(String name)``. Width is in
        the font's own units (1/1000 em for Type 1 / CFF, design units
        for TrueType — divide by ``unitsPerEm`` to normalise).
        """
        ...

    def has_glyph(self, name: str) -> bool:
        """Return ``True`` iff the font has a real glyph called ``name``.

        Mirrors upstream ``boolean hasGlyph(String name)``. Should
        return ``False`` for ``.notdef`` aliases that resolve to the
        missing-glyph slot.
        """
        ...


__all__ = ["FontBoxFont"]
