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
       positions.
    3. If the runs share a baseline within a small tolerance — either
       Y-difference is below 0.1 or one run's baseline falls inside the
       other's vertical extent — order by directional X.
    4. Otherwise, order by directional Y (top-to-bottom in reading
       order).

    Coordinate-frame note (lite carve-out)
    --------------------------------------
    Upstream's ``TextPositionComparator`` assumes ``getYDirAdj()`` is in
    a "y points down, 0,0 is upper-left" frame, so its top edge is
    ``bottom - height`` and "top first" means the *smaller* Y. pypdfbox's
    :meth:`TextPosition.get_y_dir_adj` deliberately stays in the PDF
    user-space (y-up) frame at ``dir == 0`` — the documented lite-port
    carve-out (see ``CHANGES.md`` /
    ``tests/text/upstream/test_text_position_directional.py``). Feeding
    upstream's verbatim y-down formula y-up data inverts the vertical
    ordering, so this comparator applies the y-up mirror to match the
    data the rest of pypdfbox emits (and the internal extraction-path
    comparator ``PDFTextStripper._compare_reading_order``): a run's top
    edge is ``baseline + height_dir`` and a vertically-disjoint pair is
    ordered with the *larger* Y (geometrically higher) first.
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

        # Step 2: directional coordinates. In the lite y-up frame the
        # directional Y is the run baseline; a larger Y is higher on the
        # page.
        x1 = pos1.get_x_dir_adj()
        x2 = pos2.get_x_dir_adj()
        y1 = pos1.get_y_dir_adj()
        y2 = pos2.get_y_dir_adj()

        # Top edges in the y-up frame: ``baseline + height`` (one line
        # height above the baseline), the mirror of upstream's y-down
        # ``baseline - height``.
        y1_top = y1 + pos1.get_height_dir()
        y2_top = y2 + pos2.get_height_dir()

        y_difference = abs(y1 - y2)

        # Step 3: same-line tolerance / vertical-extent overlap — order
        # by X. The two overlap clauses are the y-up transform of
        # upstream's ``overlap`` (substitute ``device_y = -user_y``).
        if (
            y_difference < self._Y_TOLERANCE
            or (y1 <= y2 <= y1_top)
            or (y2 <= y1 <= y2_top)
        ):
            if x1 < x2:
                return -1
            if x1 > x2:
                return 1
            return 0

        # Step 4: different lines — top-to-bottom means larger Y first.
        if y1 > y2:
            return -1
        return 1

    def __call__(self, pos1: TextPosition, pos2: TextPosition) -> int:
        """Alias for :meth:`compare` so the comparator can be passed
        directly to :func:`functools.cmp_to_key` without a lambda
        wrapper.
        """
        return self.compare(pos1, pos2)


__all__ = ["TextPositionComparator"]
