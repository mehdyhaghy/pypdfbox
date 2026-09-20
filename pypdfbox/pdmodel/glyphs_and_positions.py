"""Glyph / position container handed to a glyph-layout processor.

Mirrors ``org.apache.pdfbox.pdmodel.GlyphsAndPositions``
(PDFBox 3.0.9-SNAPSHOT,
``pdfbox/src/main/java/org/apache/pdfbox/pdmodel/GlyphsAndPositions.java``).

Introduced upstream for PDFBOX-4951 ("Sequences of DIN 91379 with combining
letters are rendered incorrectly"). A glyph-layout backend fills one of these
with alternating runs of adjacent glyph ids and inter-run position
adjustments, then hands it to
:meth:`~pypdfbox.pdmodel.content_stream_for_glyph_layout_interface.ContentStreamForGlyphLayoutInterface.show_glyphs_with_positioning`
which renders it as a ``TJ`` array.
"""

from __future__ import annotations

from typing import Any

__all__ = ["GlyphsAndPositions"]


class GlyphsAndPositions:
    """Stores sublists of glyphs and positions in a list.

    Mirrors upstream's ``GlyphsAndPositions`` (Java lines 27-98). The
    backing list alternates between :class:`GlyphSubList` entries (runs of
    adjacent glyph ids) and ``float`` position adjustments, exactly like
    the ``Object[]`` upstream builds.
    """

    class GlyphSubList(list):
        """Sublist to store adjacent glyphs.

        Mirrors upstream's ``public static class GlyphSubList extends
        ArrayList<Integer>`` (Java lines 33-51). Subclassing :class:`list`
        keeps the "is-a list of glyph ids" relationship upstream relies on
        for its ``instanceof`` dispatch in
        ``PDAbstractContentStream.showGlyphsWithPositioning``.
        """

        def to_int_array(self) -> list[int]:
            """Create an int array containing the elements of the list.

            Mirrors ``toIntArray()`` (Java lines 44-50). Java's ``int[]``
            maps to a plain Python ``list[int]``.
            """
            return [int(value) for value in self]

    def __init__(self) -> None:
        self._list: list[Any] = []

    def add(self, value: int | float) -> None:
        """Add a glyph (``int``) or a position (``float``).

        Upstream declares two overloads — ``add(Integer glyph)`` (Java lines
        58-73) and ``add(Float position)`` (Java lines 80-83). Java resolves
        them statically on the boxed argument type; Python dispatches on the
        runtime type instead, which yields the same partitioning because
        Python's ``int`` / ``float`` distinction matches Java's
        ``Integer`` / ``Float`` distinction.

        A glyph is appended to the trailing :class:`GlyphSubList`, starting a
        new one when the last entry is a position (or the list is empty). A
        position is appended directly.
        """
        if isinstance(value, bool):
            # ``bool`` is a subclass of ``int`` in Python but has no Java
            # counterpart here — reject it rather than silently emitting
            # glyph id 0 / 1.
            raise TypeError(
                "GlyphsAndPositions.add expects an int glyph id or a float "
                "position; got bool"
            )
        if isinstance(value, int):
            last = self._list[-1] if self._list else None
            if not isinstance(last, GlyphsAndPositions.GlyphSubList):
                glyph_sub_list = GlyphsAndPositions.GlyphSubList()
                self._list.append(glyph_sub_list)
            else:
                glyph_sub_list = last
            glyph_sub_list.append(value)
            return
        if isinstance(value, float):
            self._list.append(value)
            return
        raise TypeError(
            "GlyphsAndPositions.add expects an int glyph id or a float "
            f"position; got {type(value).__name__}"
        )

    def is_empty(self) -> bool:
        """``True`` when nothing has been added. Mirrors ``isEmpty()``
        (Java lines 89-92)."""
        return not self._list

    def clear(self) -> None:
        """Clear the list. Mirrors ``clear()`` (Java lines 97-100)."""
        self._list.clear()

    def to_array(self) -> list[Any]:
        """Convert to a list of :class:`GlyphSubList` and ``float`` entries.

        Mirrors ``toArray()`` (Java lines 107-110). Upstream returns a fresh
        ``Object[]`` taken from an unmodifiable view, so mutating the result
        never touches this instance — the returned list is a shallow copy
        for the same reason.
        """
        return list(self._list)
