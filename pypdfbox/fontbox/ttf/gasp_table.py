from typing import TYPE_CHECKING

from .ttf_table import TTFTable

if TYPE_CHECKING:
    from .true_type_font import TrueTypeFont
    from .ttf_data_stream import TTFDataStream


class GaspTable(TTFTable):
    """``gasp`` — the Grid-fitting And Scan-conversion Procedure table.

    Mirrors ``org.apache.fontbox.ttf.GaspTable``. Maps ppem ranges to
    flags that say whether to grid-fit (hint) and/or anti-alias.
    """

    TAG: str = "gasp"

    # Use grid-fitting (i.e. execute the hinting bytecode) at this size.
    GASP_GRIDFIT: int = 0x0001
    # Use grayscale (anti-aliased) rendering at this size.
    GASP_DOGRAY: int = 0x0002
    # Use grid-fitting with ClearType symmetric smoothing (gasp version 1).
    GASP_SYMMETRIC_GRIDFIT: int = 0x0004
    # Use smoothing along multiple axes with ClearType (gasp version 1).
    GASP_SYMMETRIC_SMOOTHING: int = 0x0008

    def __init__(self) -> None:
        super().__init__()
        self._tag = self.TAG
        self._version: int = 0
        self._range_max_ppem: list[int] | None = None
        self._range_flags: list[int] | None = None

    def read(self, ttf: TrueTypeFont, data: TTFDataStream) -> None:
        """Read the version, range count and ``(maxPPEM, flags)`` records."""
        self._version = data.read_unsigned_short()
        num_ranges = data.read_unsigned_short()
        range_max_ppem: list[int] = []
        range_flags: list[int] = []
        for _ in range(num_ranges):
            range_max_ppem.append(data.read_unsigned_short())
            range_flags.append(data.read_unsigned_short())
        self._range_max_ppem = range_max_ppem
        self._range_flags = range_flags
        self.initialized = True

    def get_version(self) -> int:
        """Return the table version (0 or 1)."""
        return self._version

    def get_range_max_ppem(self) -> list[int] | None:
        """Return the upper ppem bound of each range, in ascending order."""
        return self._range_max_ppem

    def get_range_flags(self) -> list[int] | None:
        """Return the flags for each range, parallel to :meth:`get_range_max_ppem`."""
        return self._range_flags

    def get_flags(self, ppem: int) -> int:
        """Return the flags of the first range whose maximum ppem is >= ``ppem``.

        Returns 0 if the table has no ranges.
        """
        if self._range_max_ppem is None or self._range_flags is None:
            return 0
        for max_ppem, flags in zip(self._range_max_ppem, self._range_flags, strict=False):
            if ppem <= max_ppem:
                return flags
        # beyond the last range (should not happen as the last bound is 0xFFFF)
        return self._range_flags[-1] if self._range_flags else 0

    def is_grid_fit(self, ppem: int) -> bool:
        """``True`` if :attr:`GASP_GRIDFIT` is set for ``ppem``."""
        return (self.get_flags(ppem) & self.GASP_GRIDFIT) != 0


__all__ = ["GaspTable"]
