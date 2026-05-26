from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.jbig2.segment_data import SegmentData
from pypdfbox.jbig2.util.combination_operator import CombinationOperator

if TYPE_CHECKING:
    from pypdfbox.jbig2.io.sub_input_stream import SubInputStream
    from pypdfbox.jbig2.segment_header import SegmentHeader


class RegionSegmentInformation(SegmentData):
    """Represents the "Region segment information" field, 7.4.1 (page 50).

    Every region segment data starts with this part.
    Mirrors ``org.apache.pdfbox.jbig2.segments.RegionSegmentInformation``.
    """

    def __init__(self, sub_input_stream: SubInputStream | None = None) -> None:
        self.sub_input_stream = sub_input_stream

        # Region segment bitmap width, 7.4.1.1
        self.bitmap_width = 0
        # Region segment bitmap height, 7.4.1.2
        self.bitmap_height = 0
        # Region segment bitmap X location, 7.4.1.3
        self.x_location = 0
        # Region segment bitmap Y location, 7.4.1.4
        self.y_location = 0
        # Region segment flags, 7.4.1.5
        self.combination_operator: CombinationOperator | None = None

    def parse_header(self) -> None:
        self.bitmap_width = int(self.sub_input_stream.read_bits(32) & 0xFFFFFFFF)
        self.bitmap_height = int(self.sub_input_stream.read_bits(32) & 0xFFFFFFFF)
        self.x_location = int(self.sub_input_stream.read_bits(32) & 0xFFFFFFFF)
        self.y_location = int(self.sub_input_stream.read_bits(32) & 0xFFFFFFFF)

        # Bit 3-7
        self.sub_input_stream.read_bits(5)  # Dirty read... reserved bits are 0

        # Bit 0-2
        self._read_combination_operator()

    def _read_combination_operator(self) -> None:
        self.combination_operator = CombinationOperator.translate_operator_code_to_enum(
            int(self.sub_input_stream.read_bits(3) & 0xF)
        )

    def init(self, header: SegmentHeader, sis: SubInputStream) -> None:
        # Upstream's init() is intentionally empty; RegionSegmentInformation is
        # constructed with the stream and driven via parse_header().
        pass

    def set_bitmap_width(self, bitmap_width: int) -> None:
        self.bitmap_width = bitmap_width

    def get_bitmap_width(self) -> int:
        return self.bitmap_width

    def set_bitmap_height(self, bitmap_height: int) -> None:
        self.bitmap_height = bitmap_height

    def get_bitmap_height(self) -> int:
        return self.bitmap_height

    def get_x_location(self) -> int:
        return self.x_location

    def get_y_location(self) -> int:
        return self.y_location

    def get_combination_operator(self) -> CombinationOperator | None:
        return self.combination_operator
