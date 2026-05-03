"""Font-like protocol shared by :class:`PDFont` and :class:`PDType3CharProc`.

Mirrors ``org.apache.pdfbox.pdmodel.font.PDFontLike`` from upstream Apache
PDFBox 3.0. Upstream Java declares this as an ``interface``; we use
``typing.Protocol`` (runtime-checkable) so the existing pypdfbox font
classes — :class:`pypdfbox.pdmodel.font.PDFont` and its subclasses, plus
:class:`pypdfbox.pdmodel.font.PDType3CharProc`-derived shapes that
expose the same surface — already satisfy the protocol without touching
their MRO.

Upstream method names (all camelCase) are mapped to snake_case per the
project porting rules:

- ``getName``                → :meth:`get_name`
- ``getFontDescriptor``      → :meth:`get_font_descriptor`
- ``getFontMatrix``          → :meth:`get_font_matrix`
- ``getBoundingBox``         → :meth:`get_bounding_box`
- ``getPositionVector``      → :meth:`get_position_vector`
- ``getHeight``              → :meth:`get_height` (deprecated, see below)
- ``getWidth``               → :meth:`get_width`
- ``hasExplicitWidth``       → :meth:`has_explicit_width`
- ``getWidthFromFont``       → :meth:`get_width_from_font`
- ``isEmbedded``             → :meth:`is_embedded`
- ``isDamaged``              → :meth:`is_damaged`
- ``getAverageFontWidth``    → :meth:`get_average_font_width`

Java ``IOException`` raised by upstream accessors maps to :class:`OSError`
per the project's Java→Python exception mapping.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class PDFontLike(Protocol):
    """Protocol for any object that "behaves like a PDF font".

    Java upstream:
        ``public interface PDFontLike`` in
        ``org.apache.pdfbox.pdmodel.font`` (Apache PDFBox 3.0,
        ``pdfbox/src/main/java/org/apache/pdfbox/pdmodel/font/PDFontLike.java``).

    The two upstream implementors are :class:`PDFont` (concrete font
    dictionary wrapper) and :class:`PDType3CharProc` (a single Type 3
    glyph stream that masquerades as a font for the purposes of width
    measurement). pypdfbox mirrors both and either satisfies the
    protocol via duck typing.
    """

    def get_name(self) -> str | None:
        """Return the font's PostScript ``BaseName`` (Type 1 / TrueType /
        Type 0) or its Type 3 ``Name``. May return ``None`` when neither
        entry is present in the underlying font dictionary.

        Mirrors upstream ``String getName()``.
        """
        ...

    def get_font_descriptor(self) -> Any:
        """Return the font descriptor, or ``None`` when absent.

        Mirrors upstream ``PDFontDescriptor getFontDescriptor()``. The
        return type is left as ``Any`` so :class:`PDFont` subclasses can
        return their concrete :class:`PDFontDescriptor` instances and
        :class:`PDType3CharProc` can return the descriptor of its
        enclosing Type 3 font without a circular type dependency.
        """
        ...

    def get_font_matrix(self) -> Any:
        """Return the font matrix that maps glyph space to text space.

        Mirrors upstream ``Matrix getFontMatrix()``. Upstream returns
        :class:`org.apache.pdfbox.util.Matrix`; pypdfbox font classes
        currently expose the matrix as a 6-element ``list[float]``
        (``[a, b, c, d, e, f]``) — typed as ``Any`` so either shape
        satisfies the protocol.
        """
        ...

    def get_bounding_box(self) -> Any:
        """Return the font's bounding box.

        Mirrors upstream ``BoundingBox getBoundingBox() throws IOException``.
        Upstream returns :class:`org.apache.fontbox.util.BoundingBox`;
        pypdfbox callers typically receive either that shape or a
        4-tuple ``(xmin, ymin, xmax, ymax)`` — typed as ``Any``.

        :raises OSError: when the bounding box cannot be read from the
            embedded font program.
        """
        ...

    def get_position_vector(self, code: int) -> Any:
        """Return the position vector ``v`` (in text space) for the glyph at
        character code ``code``.

        Mirrors upstream ``Vector getPositionVector(int code)``. For
        horizontal writing this is always ``(0, 0)``; for vertical
        writing both components are populated.
        """
        ...

    def get_height(self, code: int) -> float:
        """Return the height of the glyph at character code ``code``,
        in glyph space.

        Mirrors upstream ``float getHeight(int code) throws IOException``.

        .. deprecated:: 2.0
            Upstream marked this deprecated in PDFBox 2.0 because the
            returned value has no consistent meaning. Prefer
            :meth:`get_bounding_box` and read its height. Retained on
            the protocol because :class:`PDFont` subclasses still
            implement it for source-level parity.

        :raises OSError: when the glyph height cannot be read.
        """
        ...

    def get_width(self, code: int) -> float:
        """Return the advance width of the glyph at character code ``code``,
        in glyph space (1/1000 em for most fonts).

        Mirrors upstream ``float getWidth(int code) throws IOException``.

        :raises OSError: when the width cannot be read from either the
            font dictionary's ``/Widths`` entry or the embedded font
            program.
        """
        ...

    def has_explicit_width(self, code: int) -> bool:
        """Return ``True`` when the font dictionary specifies an explicit
        width for ``code`` via ``/Widths`` (simple fonts) or ``/W``
        (CID fonts) — but **not** the default-width fallback
        (``/MissingWidth`` / ``/DW``).

        Mirrors upstream ``boolean hasExplicitWidth(int code) throws IOException``.

        :raises OSError: when the font dictionary cannot be read.
        """
        ...

    def get_width_from_font(self, code: int) -> float:
        """Return the advance width of the glyph at character code ``code``
        as read directly from the embedded font program (not the
        ``/Widths`` array).

        Mirrors upstream ``float getWidthFromFont(int code) throws IOException``.

        :raises OSError: when the font program cannot be read.
        """
        ...

    def is_embedded(self) -> bool:
        """Return ``True`` when the font program is embedded in the PDF.

        Mirrors upstream ``boolean isEmbedded()``.
        """
        ...

    def is_damaged(self) -> bool:
        """Return ``True`` when the embedded font program is damaged
        (e.g. truncated, malformed, or fails to parse).

        Mirrors upstream ``boolean isDamaged()``.
        """
        ...

    def get_average_font_width(self) -> float:
        """Return the average advance width across all glyphs in the font,
        in 1/1000 text-space units.

        Mirrors upstream ``float getAverageFontWidth()``. Note: upstream's
        own comment flags this metric as "highly suspicious" — most
        callers should prefer :meth:`get_width` per glyph. Retained for
        source-level parity.
        """
        ...


__all__ = ["PDFontLike"]
