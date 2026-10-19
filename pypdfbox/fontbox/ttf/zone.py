"""A set of points the TrueType interpreter can manipulate.

Either zone 0 (the twilight zone, holding phantom reference points) or zone 1
(the glyph's own outline points plus its appended phantom points). Each point
has its scaled-but-unhinted "original" position and a "current" position the
bytecode moves, both in F26Dot6, plus per-axis touch flags used by
interpolation.

The coordinate and flag arrays are flat Python lists returned by reference,
exactly like upstream's ``int[]`` / ``boolean[]`` getters, so callers and the
interpreter index and mutate them in place.
"""

from __future__ import annotations


class Zone:
    """Mirrors upstream package-private ``Zone``."""

    __slots__ = (
        "_contour_ends",
        "_current_x",
        "_current_y",
        "_on_curve",
        "_original_x",
        "_original_y",
        "_point_count",
        "_touched_x",
        "_touched_y",
        "_unscaled_x",
        "_unscaled_y",
    )

    def __init__(self, point_count: int, contour_count: int) -> None:
        """Allocates a zone of the given size.

        ``point_count`` includes any phantom points; ``contour_count`` is 0
        for the twilight zone.
        """
        if point_count < 0 or contour_count < 0:
            # Java's new int[-1] throws NegativeArraySizeException
            raise ValueError("negative zone size")
        self._point_count = point_count
        self._current_x = [0] * point_count
        self._current_y = [0] * point_count
        self._original_x = [0] * point_count
        self._original_y = [0] * point_count
        self._unscaled_x = [0] * point_count
        self._unscaled_y = [0] * point_count
        self._touched_x = [False] * point_count
        self._touched_y = [False] * point_count
        self._on_curve = [False] * point_count
        self._contour_ends = [0] * contour_count

    def reset(self) -> None:
        """Zeroes every coordinate and flag.

        The twilight zone outlives a single program run - it is owned by the
        interpreter so values ``prep`` puts there survive into each glyph
        program - so it is reset rather than reallocated when the size
        changes, as FreeType does in ``tt_size_run_prep``. The lists are
        cleared in place so references handed out earlier stay valid.
        """
        n = self._point_count
        zeros = [0] * n
        falses = [False] * n
        self._current_x[:] = zeros
        self._current_y[:] = zeros
        self._original_x[:] = zeros
        self._original_y[:] = zeros
        self._unscaled_x[:] = zeros
        self._unscaled_y[:] = zeros
        self._touched_x[:] = falses
        self._touched_y[:] = falses
        self._on_curve[:] = falses
        self._contour_ends[:] = [0] * len(self._contour_ends)

    def get_point_count(self) -> int:
        """Returns the number of points in this zone."""
        return self._point_count

    def get_current_x(self) -> list[int]:
        """Returns the current (hinted) x coordinates in F26Dot6."""
        return self._current_x

    def get_current_y(self) -> list[int]:
        """Returns the current (hinted) y coordinates in F26Dot6."""
        return self._current_y

    def get_original_x(self) -> list[int]:
        """Returns the original (scaled, unhinted) x coordinates in F26Dot6."""
        return self._original_x

    def get_original_y(self) -> list[int]:
        """Returns the original (scaled, unhinted) y coordinates in F26Dot6."""
        return self._original_y

    def get_unscaled_x(self) -> list[int]:
        """Returns the original *unscaled* x coordinates in font units.

        Interpolation and relative measurements use these for the ratio,
        matching FreeType's ``orus``, because the unrounded font-unit values
        preserve precision the scaled F26Dot6 originals would lose.
        """
        return self._unscaled_x

    def get_unscaled_y(self) -> list[int]:
        """Returns the original unscaled y coordinates in font units."""
        return self._unscaled_y

    def get_touched_x(self) -> list[bool]:
        """Returns per-point touch flags for the x axis."""
        return self._touched_x

    def get_touched_y(self) -> list[bool]:
        """Returns per-point touch flags for the y axis."""
        return self._touched_y

    def get_on_curve(self) -> list[bool]:
        """Returns per-point on-curve flags."""
        return self._on_curve

    def get_contour_ends(self) -> list[int]:
        """Returns the index of the last point of each contour."""
        return self._contour_ends


__all__ = ["Zone"]
