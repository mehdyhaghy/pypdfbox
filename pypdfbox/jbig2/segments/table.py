from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.jbig2.err.invalid_header_value_exception import (
    InvalidHeaderValueException,
)
from pypdfbox.jbig2.segment_data import SegmentData

if TYPE_CHECKING:
    from pypdfbox.jbig2.io.sub_input_stream import SubInputStream
    from pypdfbox.jbig2.segment_header import SegmentHeader


def _to_signed_int(value: int) -> int:
    """Interpret the low 32 bits of ``value`` as a signed Java ``int``."""
    value &= 0xFFFFFFFF
    return value - 0x100000000 if value >= 0x80000000 else value


class Table(SegmentData):
    """Represents a "Table" segment. It handles custom tables, see Annex B.

    Mirrors ``org.apache.pdfbox.jbig2.segments.Table`` (segment type 53).
    """

    def __init__(self) -> None:
        self.sub_input_stream: SubInputStream | None = None

        # Code table flags, B.2.1, page 87
        self.ht_out_of_band = 0
        self.ht_ps = 0
        self.ht_rs = 0

        # Code table lowest value, B.2.2, page 87
        self.ht_low = 0

        # Code table highest value, B.2.3, page 87
        self.ht_high = 0

    def _parse_header(self) -> None:
        # Bit 7
        bit = self.sub_input_stream.read_bit()
        if bit == 1:
            raise InvalidHeaderValueException(
                f"B.2.1 Code table flags: Bit 7 must be zero, but was {bit}"
            )

        # Bit 4-6
        self.ht_rs = int((self.sub_input_stream.read_bits(3) + 1) & 0xF)

        # Bit 1-3
        self.ht_ps = int((self.sub_input_stream.read_bits(3) + 1) & 0xF)

        # Bit 0
        self.ht_out_of_band = self.sub_input_stream.read_bit()

        # Upstream casts (int) over the 32 read bits, sign-extending the value
        # to a signed Java int; the table bounds may be negative.
        self.ht_low = _to_signed_int(self.sub_input_stream.read_bits(32))
        self.ht_high = _to_signed_int(self.sub_input_stream.read_bits(32))

    def init(self, header: SegmentHeader, sis: SubInputStream) -> None:
        self.sub_input_stream = sis
        self._parse_header()

    def get_ht_oob(self) -> int:
        return self.ht_out_of_band

    def get_ht_ps(self) -> int:
        return self.ht_ps

    def get_ht_rs(self) -> int:
        return self.ht_rs

    def get_ht_low(self) -> int:
        return self.ht_low

    def get_ht_high(self) -> int:
        return self.ht_high

    def get_sub_input_stream(self) -> SubInputStream:
        return self.sub_input_stream
