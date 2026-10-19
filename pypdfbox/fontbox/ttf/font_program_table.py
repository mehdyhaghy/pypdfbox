from typing import TYPE_CHECKING

from .ttf_table import TTFTable

if TYPE_CHECKING:
    from .true_type_font import TrueTypeFont
    from .ttf_data_stream import TTFDataStream


class FontProgramTable(TTFTable):
    """``fpgm`` — the Font Program table.

    Mirrors ``org.apache.fontbox.ttf.FontProgramTable``. Holds the raw TrueType
    bytecode of the font program, run once when the font is first used
    (typically to define functions).
    """

    TAG: str = "fpgm"

    def __init__(self) -> None:
        super().__init__()
        self._tag = self.TAG
        self._program: bytes | None = None

    def read(self, ttf: TrueTypeFont, data: TTFDataStream) -> None:
        """Read the whole table body as bytecode."""
        self._program = data.read_bytes(self.get_length())
        self.initialized = True

    def get_program(self) -> bytes | None:
        """Return the raw bytecode of this program."""
        return self._program


__all__ = ["FontProgramTable"]
