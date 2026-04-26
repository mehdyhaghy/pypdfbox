from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .true_type_font import TrueTypeFont
    from .ttf_data_stream import TTFDataStream


class TTFTable:
    """Base class for every TTF table loader.

    Mirrors ``org.apache.fontbox.ttf.TTFTable``. The base class itself is used
    for unknown / unsupported table tags (it just records the tag, length and
    offset; ``read`` is a no-op).
    """

    def __init__(self) -> None:
        self._tag: str = ""
        self._check_sum: int = 0
        self._offset: int = 0
        self._length: int = 0
        self.initialized: bool = False

    # ---- accessors ----
    def get_tag(self) -> str:
        return self._tag

    def set_tag(self, value: str) -> None:
        self._tag = value

    def get_check_sum(self) -> int:
        return self._check_sum

    def set_check_sum(self, value: int) -> None:
        self._check_sum = value

    def get_offset(self) -> int:
        return self._offset

    def set_offset(self, value: int) -> None:
        self._offset = value

    def get_length(self) -> int:
        return self._length

    def set_length(self, value: int) -> None:
        self._length = value

    def get_initialized(self) -> bool:
        return self.initialized

    # ---- override points ----
    def read(self, ttf: TrueTypeFont, data: TTFDataStream) -> None:  # noqa: ARG002
        """Read this table from the data stream. Default: no-op (unknown tag)."""
        # do not flip ``initialized`` for the unknown-table base implementation;
        # the field is intentionally not set so callers know the body wasn't read.
