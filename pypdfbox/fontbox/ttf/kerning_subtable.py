from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .true_type_font import TrueTypeFont


class KerningSubtable:
    """A single subtable of a TrueType ``kern`` table.

    Mirrors ``org.apache.fontbox.ttf.KerningSubtable`` at the public-method
    level. The on-disk parsing is delegated to ``fontTools.ttLib`` (its
    ``KernTable_format_0`` already understands both OpenType and Apple
    layouts); this class is only an API shim that re-exposes the fields
    PDFBox callers expect (``isHorizontalKerning``, ``getKerning``,
    etc.) snake-cased.

    Only the upstream-supported case (OpenType ``kern`` version 0,
    subtable format 0) carries pair data — formats 1 / 2 / Apple
    extended-format subtables are exposed but report ``get_kerning``
    of 0 for any pair, matching upstream's "unsupported subtable"
    behaviour where ``pairs`` stays ``None`` and the warning is logged.
    """

    # Coverage bit masks / shifts — kept identical to upstream so callers
    # that go looking for the constants find them in the expected place.
    COVERAGE_HORIZONTAL: int = 0x0001
    COVERAGE_MINIMUMS: int = 0x0002
    COVERAGE_CROSS_STREAM: int = 0x0004
    COVERAGE_FORMAT: int = 0xFF00

    COVERAGE_HORIZONTAL_SHIFT: int = 0
    COVERAGE_MINIMUMS_SHIFT: int = 1
    COVERAGE_CROSS_STREAM_SHIFT: int = 2
    COVERAGE_FORMAT_SHIFT: int = 8

    def __init__(
        self,
        ft_subtable: Any,
        ttf: TrueTypeFont | None = None,
    ) -> None:
        # ft_subtable is a fontTools KernTable_format_0 (or
        # KernTable_format_unkown) instance. We pull only what's needed
        # to evaluate coverage flags and look up a pair value.
        self._ft = ft_subtable
        self._ttf = ttf

        # In fontTools, OpenType non-Apple ``coverage`` is the low byte
        # of the upstream 16-bit coverage word and ``format`` is the high
        # byte. Re-encode them into the upstream layout so the bit-mask
        # constants above are still meaningful for callers that read
        # ``self._coverage`` directly.
        ft_coverage = int(getattr(ft_subtable, "coverage", 0))
        ft_format = int(getattr(ft_subtable, "format", 0))
        if getattr(ft_subtable, "apple", False):
            # Apple uses an 8-bit coverage byte where bit 7 is "horizontal"
            # (inverted relative to OpenType) and bits 13-15 carry the
            # cross-stream / variation flags. We do not currently support
            # Apple-style kern subtables for ``getKerning`` lookup
            # anyway — leave coverage as exposed by fontTools, and the
            # horizontal/minimums/cross-stream booleans below stay False.
            self._coverage = ft_coverage
            self._horizontal = False
            self._minimums = False
            self._cross_stream = False
        else:
            self._coverage = ((ft_format & 0xFF) << 8) | (ft_coverage & 0xFF)
            self._horizontal = (
                self._coverage & self.COVERAGE_HORIZONTAL
            ) >> self.COVERAGE_HORIZONTAL_SHIFT != 0
            self._minimums = (
                self._coverage & self.COVERAGE_MINIMUMS
            ) >> self.COVERAGE_MINIMUMS_SHIFT != 0
            self._cross_stream = (
                self._coverage & self.COVERAGE_CROSS_STREAM
            ) >> self.COVERAGE_CROSS_STREAM_SHIFT != 0

        self._format = ft_format
        # ``pairs`` mirrors upstream: only populated for format 0; any
        # other format leaves it None, and getKerning then returns 0.
        kern_table = getattr(ft_subtable, "kernTable", None)
        if self._format == 0 and isinstance(kern_table, dict):
            self._pairs = kern_table
        else:
            self._pairs = None

    # ---------- coverage accessors ----------

    def is_horizontal_kerning(self, cross: bool = False) -> bool:
        """True if the subtable describes inline-progression kerning for
        horizontal writing modes (i.e. ``getKerning`` returns useful pair
        adjustments for horizontal text layout).

        With ``cross=False`` (default), require the cross-stream flag to
        be unset; with ``cross=True``, require it to be set. In either
        case minimum-value subtables are excluded.
        """
        if not self._horizontal:
            return False
        if self._minimums:
            return False
        if cross:
            return self._cross_stream
        return not self._cross_stream

    def is_horizontal(self) -> bool:
        """Raw value of the coverage ``horizontal`` bit."""
        return self._horizontal

    def is_minimum(self) -> bool:
        """Raw value of the coverage ``minimums`` bit."""
        return self._minimums

    def is_cross_stream(self) -> bool:
        """Raw value of the coverage ``cross-stream`` bit."""
        return self._cross_stream

    def get_format(self) -> int:
        """Subtable format (0 / 1 / 2 / 3)."""
        return self._format

    def get_coverage(self) -> int:
        """Reconstructed 16-bit upstream coverage word (format in high byte,
        flags in low byte)."""
        return self._coverage

    # ---------- pair lookup ----------

    def get_kerning(self, *args: Any) -> Any:
        """Look up a kerning adjustment.

        Two call shapes mirror upstream Java overloads:

        * ``get_kerning(left_gid, right_gid)`` -> int. Returns the kerning
          adjustment for that ordered pair, in font design units. Returns
          0 when the pair is absent or the subtable format is unsupported.
        * ``get_kerning(glyphs)`` -> list[int]. Given a sequence of glyph
          IDs, returns a list of adjustments where the Nth entry is the
          adjustment between glyph N and the next non-negative glyph in
          the sequence; matches upstream ``getKerning(int[])``.
        """
        if len(args) == 1:
            return self._get_kerning_seq(args[0])
        if len(args) == 2:
            left, right = args
            return self._get_kerning_pair(int(left), int(right))
        raise TypeError(
            f"get_kerning() takes 1 or 2 positional args, got {len(args)}"
        )

    def _get_kerning_pair(self, left: int, right: int) -> int:
        if self._pairs is None or left < 0 or right < 0:
            return 0
        # fontTools stores keys as (glyph_name, glyph_name) tuples — we
        # need to project the GIDs back through the glyph order to look
        # them up.
        if self._ttf is None:
            return 0
        glyph_order = self._ttf._tt.getGlyphOrder()  # noqa: SLF001
        if left >= len(glyph_order) or right >= len(glyph_order):
            return 0
        key = (glyph_order[left], glyph_order[right])
        value = self._pairs.get(key)
        if value is None:
            return 0
        return int(value)

    def _get_kerning_seq(self, glyphs: list[int] | tuple[int, ...]) -> list[int]:
        result: list[int] = []
        if self._pairs is None:
            return [0] * len(glyphs)
        ng = len(glyphs)
        for i in range(ng):
            left = int(glyphs[i])
            right = -1
            for k in range(i + 1, ng):
                g = int(glyphs[k])
                if g >= 0:
                    right = g
                    break
            result.append(self._get_kerning_pair(left, right))
        return result


__all__ = ["KerningSubtable"]
