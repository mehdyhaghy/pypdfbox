from typing import TYPE_CHECKING

from .ttf_table import TTFTable

if TYPE_CHECKING:
    from .true_type_font import TrueTypeFont
    from .ttf_data_stream import TTFDataStream


class ControlValueTable(TTFTable):
    """``cvt `` — the Control Value table.

    Mirrors ``org.apache.fontbox.ttf.ControlValueTable``. Holds the raw
    control values (signed FWords, in font units) read by the TrueType
    hinting interpreter, which scales them to the active ppem.
    """

    TAG: str = "cvt "

    def __init__(self) -> None:
        super().__init__()
        self._tag = self.TAG
        self._values: list[int] | None = None

    def read(self, ttf: TrueTypeFont, data: TTFDataStream) -> None:
        """Read ``length / 2`` signed shorts from ``data``."""
        count = self.get_length() // 2
        self._values = [data.read_signed_short() for _ in range(count)]
        self.initialized = True

    def get_values(self) -> list[int] | None:
        """Return the raw control values in font units (FWords)."""
        return self._values

    def get_value_count(self) -> int:
        """Return the number of control values in this table."""
        return len(self._values) if self._values is not None else 0


__all__ = ["ControlValueTable"]
