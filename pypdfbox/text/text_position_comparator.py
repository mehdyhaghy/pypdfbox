"""Reading-order comparator for :class:`TextPosition` instances.

Mirrors ``org.apache.pdfbox.text.TextPositionComparator`` from upstream
PDFBox 3.0.x. Upstream's class ``implements
java.util.Comparator<TextPosition>`` and is used by
``PDFTextStripper.writePage`` to order glyphs into a single reading
stream when ``sortByPosition`` is enabled.

Why a separate class
--------------------
PDFs with mixed-direction text (e.g. a portrait page with a sideways
caption) need to be ordered first by *direction* — runs that share a
direction can then be sorted along that direction's reading axis.
Within a single direction the comparator falls back to Y (top-to-bottom
on the rotated frame) and X (left-to-right on the rotated frame) using
the directional adjustments :meth:`TextPosition.get_x_dir_adj` and
:meth:`TextPosition.get_y_dir_adj`.

Lite-mode caveat
----------------
The lite ``PDFTextStripper.writePage`` walks tokens in stream order and
does not invoke this comparator by default — sorting is opt-in via
:meth:`PDFTextStripper.set_sort_by_position`. The comparator is exposed
as a standalone helper so callers porting upstream Java code that uses
``Collections.sort(positions, new TextPositionComparator())`` have a
direct snake_case equivalent: ``positions.sort(key=cmp_to_key(
TextPositionComparator()))``.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .text_position import TextPosition


class TextPositionComparator:
    """Comparator that orders text positions in reading order.

    Implements ``__call__(pos1, pos2)`` so it can be used directly with
    :func:`functools.cmp_to_key` (the typical Python idiom for sorting
    with a Java-style ``Comparator``):

        from functools import cmp_to_key
        positions.sort(key=cmp_to_key(TextPositionComparator()))

    The comparator is stateless and can be safely shared across
    threads or reused across pages.

    Algorithm (mirrors upstream)
    ----------------------------
    1. Compare by :meth:`TextPosition.get_dir`. Different directions are
       always grouped before any cross-direction sort happens.
    2. Within a direction, fetch the directional X and Y for both
       positions (already in a "y points down, 0,0 is upper-left" frame
       per the upstream contract).
    3. If the runs share a baseline within a small tolerance — either
       Y-difference is below 0.1 or one run's bottom Y falls inside the
       other's vertical extent — order by directional X.
    4. Otherwise, order by directional Y (top-to-bottom).

    The Y-overlap check uses :meth:`TextPosition.get_height_dir` to
    derive each run's top edge: ``top = bottom - height_dir`` (the
    upstream subtraction uses the upper-left-origin convention
    established by step 2).
    """

    # Tolerance (in user-space units) below which two positions are
    # treated as sharing a baseline. Mirrors the upstream literal
    # ``yDifference < .1`` check.
    _Y_TOLERANCE: float = 0.1

    def compare(self, pos1: TextPosition, pos2: TextPosition) -> int:
        """Return ``-1`` / ``0`` / ``1`` — Java ``Comparator`` semantics."""
        # Step 1: direction.
        d1 = pos1.get_dir()
        d2 = pos2.get_dir()
        if d1 < d2:
            return -1
        if d1 > d2:
            return 1

        # Step 2: directional coordinates.
        x1 = pos1.get_x_dir_adj()
        x2 = pos2.get_x_dir_adj()
        pos1_y_bottom = pos1.get_y_dir_adj()
        pos2_y_bottom = pos2.get_y_dir_adj()

        # Top edges in the "0,0 is upper-left" frame.
        pos1_y_top = pos1_y_bottom - pos1.get_height_dir()
        pos2_y_top = pos2_y_bottom - pos2.get_height_dir()

        y_difference = abs(pos1_y_bottom - pos2_y_bottom)

        # Step 3: same-line tolerance — order by X.
        if (
            y_difference < self._Y_TOLERANCE
            or (pos1_y_top <= pos2_y_bottom <= pos1_y_bottom)
            or (pos2_y_top <= pos1_y_bottom <= pos2_y_bottom)
        ):
            if x1 < x2:
                return -1
            if x1 > x2:
                return 1
            return 0

        # Step 4: different lines — order by Y (top-to-bottom).
        if pos1_y_bottom < pos2_y_bottom:
            return -1
        return 1

    def __call__(self, pos1: TextPosition, pos2: TextPosition) -> int:
        """Alias for :meth:`compare` so the comparator can be passed
        directly to :func:`functools.cmp_to_key` without a lambda
        wrapper.
        """
        return self.compare(pos1, pos2)


__all__ = ["TextPositionComparator"]
