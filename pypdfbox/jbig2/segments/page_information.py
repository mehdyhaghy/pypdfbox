from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.jbig2.segment_data import SegmentData
from pypdfbox.jbig2.util.combination_operator import CombinationOperator

if TYPE_CHECKING:
    from pypdfbox.jbig2.io.sub_input_stream import SubInputStream
    from pypdfbox.jbig2.segment_header import SegmentHeader


class PageInformation(SegmentData):
    """Represents the segment type "Page information", 7.4.8 (page 73).

    Mirrors ``org.apache.pdfbox.jbig2.segments.PageInformation``.
    """

    def __init__(self) -> None:
        self.sub_input_stream: SubInputStream | None = None

        # Page bitmap width, four byte, 7.4.8.1
        self.bitmap_width = 0
        # Page bitmap height, four byte, 7.4.8.2
        self.bitmap_height = 0
        # Page X resolution, four byte, 7.4.8.3
        self.resolution_x = 0
        # Page Y resolution, four byte, 7.4.8.4
        self.resolution_y = 0

        # Page segment flags, one byte, 7.4.8.5
        self.combination_operator_override_allowed = False
        self.combination_operator: CombinationOperator | None = None
        self.requires_auxiliary_buffer = False
        self.default_pixel_value = 0
        self.might_contain_refinements_value = False
        self.is_lossless_value = False

        # Page striping information, two byte, 7.4.8.6
        self.is_striped_value = False
        self.max_stripe_size = 0

    def _parse_header(self) -> None:
        self._read_width_and_height()
        self._read_resolution()

        # Bit 7
        self.sub_input_stream.read_bit()  # dirty read

        # Bit 6
        self._read_combination_operator_override_allowed()

        # Bit 5
        self._read_requires_auxiliary_buffer()

        # Bit 3-4
        self._read_combination_operator()

        # Bit 2
        self._read_default_pixel_value()

        # Bit 1
        self._read_contains_refinement()

        # Bit 0
        self._read_is_lossless()

        # Bit 15
        self._read_is_striped()

        # Bit 0-14
        self._read_max_stripe_size()

    def _read_resolution(self) -> None:
        self.resolution_x = int(self.sub_input_stream.read_bits(32)) & 0xFFFFFFFF
        self.resolution_y = int(self.sub_input_stream.read_bits(32)) & 0xFFFFFFFF

    def _read_combination_operator_override_allowed(self) -> None:
        # Bit 6
        if self.sub_input_stream.read_bit() == 1:
            self.combination_operator_override_allowed = True

    def _read_requires_auxiliary_buffer(self) -> None:
        # Bit 5
        if self.sub_input_stream.read_bit() == 1:
            self.requires_auxiliary_buffer = True

    def _read_combination_operator(self) -> None:
        # Bit 3-4
        self.combination_operator = CombinationOperator.translate_operator_code_to_enum(
            int(self.sub_input_stream.read_bits(2) & 0xF)
        )

    def _read_default_pixel_value(self) -> None:
        # Bit 2
        self.default_pixel_value = self.sub_input_stream.read_bit()

    def _read_contains_refinement(self) -> None:
        # Bit 1
        if self.sub_input_stream.read_bit() == 1:
            self.might_contain_refinements_value = True

    def _read_is_lossless(self) -> None:
        # Bit 0
        if self.sub_input_stream.read_bit() == 1:
            self.is_lossless_value = True

    def _read_is_striped(self) -> None:
        # Bit 15
        if self.sub_input_stream.read_bit() == 1:
            self.is_striped_value = True

    def _read_max_stripe_size(self) -> None:
        # Bit 0-14
        self.max_stripe_size = int(self.sub_input_stream.read_bits(15) & 0xFFFF)

    def _read_width_and_height(self) -> None:
        self.bitmap_width = int(self.sub_input_stream.read_bits(32))  # & 0xffffffff
        self.bitmap_height = int(self.sub_input_stream.read_bits(32))  # & 0xffffffff

    def init(self, header: SegmentHeader, sis: SubInputStream) -> None:
        self.sub_input_stream = sis
        self._parse_header()

    def get_width(self) -> int:
        return self.bitmap_width

    def get_height(self) -> int:
        return self.bitmap_height

    def get_resolution_x(self) -> int:
        return self.resolution_x

    def get_resolution_y(self) -> int:
        return self.resolution_y

    def get_default_pixel_value(self) -> int:
        return self.default_pixel_value

    def is_combination_operator_override_allowed(self) -> bool:
        return self.combination_operator_override_allowed

    def get_combination_operator(self) -> CombinationOperator | None:
        return self.combination_operator

    def is_striped(self) -> bool:
        return self.is_striped_value

    def get_max_stripe_size(self) -> int:
        return self.max_stripe_size

    def is_auxiliary_buffer_required(self) -> bool:
        return self.requires_auxiliary_buffer

    def might_contain_refinements(self) -> bool:
        return self.might_contain_refinements_value

    def is_lossless(self) -> bool:
        return self.is_lossless_value

    def _get_bitmap_width(self) -> int:
        return self.bitmap_width

    def _get_bitmap_height(self) -> int:
        return self.bitmap_height
