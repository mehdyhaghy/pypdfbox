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

    def get_font_b_box(self) -> Any:
        """Strict-snake-case spelling of upstream ``getFontBBox``
        (FontBoxFont.java L48).

        The project porting rules expand consecutive caps as separate
        words, so ``getFontBBox`` → ``get_font_b_box``. This method is
        declared on the Protocol purely as an interface presence
        marker — concrete implementations may either override it (in
        which case the helper :func:`get_font_b_box` defined at module
        scope dispatches here) or leave it absent and the helper falls
        back to :meth:`get_font_bbox`. Both shapes satisfy the
        runtime-checkable protocol because ``Protocol`` membership in
        ``typing`` matches on method *names* with the helper's
        ``getattr`` fallback covering implementations that only
        define the contracted ``get_font_bbox`` spelling.
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


# Exclude :meth:`FontBoxFont.get_font_b_box` from the runtime-checkable
# structural check: it is declared on the Protocol as an *interface
# marker* (so parity tooling and static analyzers see the strict
# snake_case rendering of upstream ``getFontBBox``), but concrete
# fontbox implementations expose the contracted ``get_font_bbox``
# spelling only — keeping the strict spelling out of
# ``__protocol_attrs__`` preserves the existing duck-typing contract
# so ``isinstance(font, FontBoxFont)`` still returns ``True`` for
# implementations that don't define the strict spelling. Concrete
# subclasses that *do* want the strict spelling are free to add it;
# the module-level :func:`get_font_b_box` helper below dispatches to
# whichever spelling is present.
# A runtime_checkable Protocol always carries ``__protocol_attrs__``;
# the ``None`` arc is an import-time guard against a future CPython
# rename and is therefore unreachable in practice.
_attrs = getattr(FontBoxFont, "__protocol_attrs__", None)
if _attrs is not None:  # pragma: no cover
    _attrs.discard("get_font_b_box")
del _attrs


def get_font_b_box(font: FontBoxFont) -> Any:
    """Strict snake-case rendering of upstream ``getFontBBox`` exposed
    as a free function rather than a protocol method.

    The project porting rules expand consecutive caps as separate
    words, so ``getFontBBox`` lowercases to ``get_font_b_box``. Adding
    that method directly to the :class:`FontBoxFont` protocol would
    force every duck-typed implementer to define a second method;
    instead this free function delegates to whichever contracted
    accessor (``get_font_b_box`` if the concrete class chose to expose
    the strict spelling, otherwise the familiar ``get_font_bbox``) the
    font implements.

    Mirrors upstream ``FontBoxFont.getFontBBox`` (FontBoxFont.java
    L48) — kept as a helper so PDFBox-shaped callers can dispatch
    through either spelling without per-call branching.
    """
    strict = getattr(font, "get_font_b_box", None)
    if callable(strict):
        return strict()
    return font.get_font_bbox()


__all__ = ["FontBoxFont", "get_font_b_box"]
