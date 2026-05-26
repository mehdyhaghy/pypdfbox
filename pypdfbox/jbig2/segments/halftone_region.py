from __future__ import annotations

import math
from typing import TYPE_CHECKING

from pypdfbox.jbig2.bitmap import Bitmap
from pypdfbox.jbig2.image.bitmaps import Bitmaps
from pypdfbox.jbig2.region import Region
from pypdfbox.jbig2.segments.generic_region import GenericRegion
from pypdfbox.jbig2.segments.region_segment_information import (
    RegionSegmentInformation,
)
from pypdfbox.jbig2.util.combination_operator import CombinationOperator

if TYPE_CHECKING:
    from pypdfbox.jbig2.io.sub_input_stream import SubInputStream
    from pypdfbox.jbig2.segment_header import SegmentHeader
    from pypdfbox.jbig2.segments.pattern_dictionary import PatternDictionary


def _to_signed_int32(value: int) -> int:
    """Interpret the low 32 bits of ``value`` as a signed Java ``int``.

    Mirrors upstream's ``(int) subInputStream.readBits(32)`` cast for HGX/HGY,
    which sign-extends the 32-bit field (the offsets may be negative).
    """
    value &= 0xFFFFFFFF
    return value - 0x1_0000_0000 if value >= 0x8000_0000 else value


class HalftoneRegion(Region):
    """The data of segment type "Halftone region".

    Parsing is described in 7.4.5, page 67. Decoding procedure in 6.6.5 and
    7.4.5.2. Mirrors ``org.apache.pdfbox.jbig2.segments.HalftoneRegion``.
    """

    def __init__(
        self,
        sub_input_stream: SubInputStream | None = None,
        segment_header: SegmentHeader | None = None,
    ) -> None:
        self.sub_input_stream = sub_input_stream
        self.segment_header = segment_header
        self.data_header_offset = 0
        self.data_header_length = 0
        self.data_offset = 0
        self.data_length = 0

        # Region segment information field, 7.4.1
        self.region_info: RegionSegmentInformation | None = None

        # Halftone segment information field, 7.4.5.1.1
        self.h_default_pixel = 0
        self.h_combination_operator: CombinationOperator | None = None
        self.h_skip_enabled = False
        self.h_template = 0
        self.is_mmr_encoded = False

        # Halftone grid position and size, 7.4.5.1.2
        # Width of the gray-scale image, 7.4.5.1.2.1
        self.h_grid_width = 0
        # Height of the gray-scale image, 7.4.5.1.2.2
        self.h_grid_height = 0
        # Horizontal offset of the grid, 7.4.5.1.2.3
        self.h_grid_x = 0
        # Vertical offset of the grid, 7.4.5.1.2.4
        self.h_grid_y = 0

        # Halftone grid vector, 7.4.5.1.3
        # Horizontal coordinate of the halftone grid vector, 7.4.5.1.3.1
        self.h_region_x = 0
        # Vertical coordinate of the halftone grid vector, 7.4.5.1.3.2
        self.h_region_y = 0

        # Decoded data
        self.halftone_region_bitmap: Bitmap | None = None

        # Previously decoded data from other regions or dictionaries, stored to
        # use as patterns in this region (HPATS).
        self.patterns: list[Bitmap] | None = None

        if sub_input_stream is not None:
            self.region_info = RegionSegmentInformation(sub_input_stream)

    def _parse_header(self) -> None:
        self.region_info.parse_header()

        # 7.4.5.1.1 Halftone region segment flags

        # Bit 7: HDEFPIXEL
        self.h_default_pixel = self.sub_input_stream.read_bit()

        # Bit 4-6: HCOMBOP
        self.h_combination_operator = (
            CombinationOperator.translate_operator_code_to_enum(
                int(self.sub_input_stream.read_bits(3) & 0xF)
            )
        )

        # Bit 3: HENABLESKIP
        if self.sub_input_stream.read_bit() == 1:
            self.h_skip_enabled = True

        # Bit 1-2: HTEMPLATE
        self.h_template = int(self.sub_input_stream.read_bits(2) & 0xF)

        # Bit 0: HMMR
        if self.sub_input_stream.read_bit() == 1:
            self.is_mmr_encoded = True

        # 7.4.5.1.2 Halftone grid position and size
        self.h_grid_width = int(self.sub_input_stream.read_bits(32) & 0xFFFFFFFF)  # HGW
        self.h_grid_height = int(
            self.sub_input_stream.read_bits(32) & 0xFFFFFFFF
        )  # HGH

        self.h_grid_x = _to_signed_int32(self.sub_input_stream.read_bits(32))  # HGX
        self.h_grid_y = _to_signed_int32(self.sub_input_stream.read_bits(32))  # HGY

        # 7.4.5.1.3 Halftone grid vector
        self.h_region_x = int(self.sub_input_stream.read_bits(16)) & 0xFFFF  # HRX
        self.h_region_y = int(self.sub_input_stream.read_bits(16)) & 0xFFFF  # HRY

        # Segment data structure
        self._compute_segment_data_structure()

    def _compute_segment_data_structure(self) -> None:
        self.data_offset = self.sub_input_stream.get_stream_position()
        self.data_header_length = self.data_offset - self.data_header_offset
        self.data_length = self.sub_input_stream.length() - self.data_header_length

    def get_region_bitmap(self) -> Bitmap:
        """Decode this halftone region. The procedure is described in 6.6.5.

        :return: The decoded :class:`Bitmap` of this region.

        :raises OSError: if an underlying IO operation fails.
        :raises InvalidHeaderValueException: if a segment header value is invalid.
        """
        if self.halftone_region_bitmap is None:
            # 6.6.5, page 40
            # 1)
            self.halftone_region_bitmap = Bitmap(
                self.region_info.get_bitmap_width(),
                self.region_info.get_bitmap_height(),
            )

            if self.patterns is None:
                self.patterns = self._get_patterns()

            if self.h_default_pixel == 1:
                self.halftone_region_bitmap.fill_bitmap(0xFF)

            # 2) 6.6.5.1 Computing HSKIP
            h_skip = None
            if self.h_skip_enabled:
                h_pattern_height = self.patterns[0].get_height()  # HPW
                h_pattern_width = self.patterns[0].get_width()  # HPH
                h_skip = self._compute_h_skip(h_pattern_width, h_pattern_height)

            # 3)
            bits_per_value = int(
                math.ceil(math.log(len(self.patterns)) / math.log(2))
            )

            # 4)
            gray_scale_values = self._gray_scale_decoding(bits_per_value, h_skip)

            # 5), rendering the pattern, described in 6.6.5.2
            self._render_pattern(gray_scale_values)

        # 6)
        return self.halftone_region_bitmap

    def _render_pattern(self, gray_scale_values: list[list[int]]) -> None:
        """Draw the pattern into the region bitmap, as described in 6.6.5.2."""
        # 1)
        for m in range(self.h_grid_height):
            # a)
            for n in range(self.h_grid_width):
                # i)
                x = self._compute_x(m, n)
                y = self._compute_y(m, n)

                # ii)
                pattern_bitmap = self.patterns[gray_scale_values[m][n]]
                Bitmaps.blit(
                    pattern_bitmap,
                    self.halftone_region_bitmap,
                    x,
                    y,
                    self.h_combination_operator,
                )

    def _get_patterns(self) -> list[Bitmap]:
        patterns: list[Bitmap] = []

        for s in self.segment_header.get_rt_segments():
            pattern_dictionary: PatternDictionary = s.get_segment_data()
            patterns.extend(pattern_dictionary.get_dictionary())

        return patterns

    def _gray_scale_decoding(
        self, bits_per_value: int, h_skip: Bitmap | None
    ) -> list[list[int]]:
        """Gray-scale image decoding procedure, described in Annex C.5 (page 98)."""
        gb_at_x: list[int] | None = None
        gb_at_y: list[int] | None = None

        if not self.is_mmr_encoded:
            gb_at_x = [0, 0, 0, 0]
            gb_at_y = [0, 0, 0, 0]
            # Set AT pixel values
            if self.h_template <= 1:
                gb_at_x[0] = 3
            elif self.h_template >= 2:
                gb_at_x[0] = 2

            gb_at_y[0] = -1
            gb_at_x[1] = -3
            gb_at_y[1] = -1
            gb_at_x[2] = 2
            gb_at_y[2] = -2
            gb_at_x[3] = -2
            gb_at_y[3] = -2

        gray_scale_planes: list[Bitmap | None] = [None] * bits_per_value

        # 1)
        generic_region = GenericRegion(self.sub_input_stream)
        generic_region.set_parameters(
            self.is_mmr_encoded,
            self.data_offset,
            self.data_length,
            self.h_grid_height,
            self.h_grid_width,
            self.h_template,
            False,
            self.h_skip_enabled,
            h_skip,
            gb_at_x,
            gb_at_y,
        )

        # 2)
        j = bits_per_value - 1

        gray_scale_planes[j] = generic_region.get_region_bitmap()

        while j > 0:
            j -= 1
            generic_region.reset_bitmap()
            # 3) a)
            gray_scale_planes[j] = generic_region.get_region_bitmap()
            # 3) b)
            gray_scale_planes = self._combine_gray_scale_planes(gray_scale_planes, j)

        # 4)
        return self._compute_gray_scale_values(gray_scale_planes, bits_per_value)

    def _combine_gray_scale_planes(
        self, gray_scale_planes: list[Bitmap], j: int
    ) -> list[Bitmap]:
        byte_index = 0
        for _y in range(gray_scale_planes[j].get_height()):
            x = 0
            while x < gray_scale_planes[j].get_width():
                new_value = gray_scale_planes[j + 1].get_byte(byte_index)
                old_value = gray_scale_planes[j].get_byte(byte_index)

                gray_scale_planes[j].set_byte(
                    byte_index,
                    Bitmaps.combine_bytes(
                        old_value, new_value, CombinationOperator.XOR
                    ),
                )
                byte_index += 1
                x += 8
        return gray_scale_planes

    def _compute_gray_scale_values(
        self, gray_scale_planes: list[Bitmap], bits_per_value: int
    ) -> list[list[int]]:
        # Gray-scale decoding procedure, page 98
        gray_scale_values = [
            [0] * self.h_grid_width for _ in range(self.h_grid_height)
        ]

        # 4)
        for y in range(self.h_grid_height):
            x = 0
            while x < self.h_grid_width:
                minor_width = 8 if self.h_grid_width - x > 8 else self.h_grid_width - x
                byte_index = gray_scale_planes[0].get_byte_index(x, y)

                for minor_x in range(minor_width):
                    i = minor_x + x
                    gray_scale_values[y][i] = 0

                    for j in range(bits_per_value):
                        gray_scale_values[y][i] += (
                            (gray_scale_planes[j].get_byte(byte_index) >> (7 - i & 7))
                            & 1
                        ) * (1 << j)
                x += 8
        return gray_scale_values

    def _compute_x(self, m: int, n: int) -> int:
        return (self.h_grid_x + m * self.h_region_y + n * self.h_region_x) >> 8

    def _compute_y(self, m: int, n: int) -> int:
        return (self.h_grid_y + m * self.h_region_x - n * self.h_region_y) >> 8

    def init(self, header: SegmentHeader, sis: SubInputStream) -> None:
        self.segment_header = header
        self.sub_input_stream = sis
        self.region_info = RegionSegmentInformation(self.sub_input_stream)
        self._parse_header()

    def get_combination_operator(self) -> CombinationOperator | None:
        return self.h_combination_operator

    def get_region_info(self) -> RegionSegmentInformation:
        return self.region_info

    def get_h_template(self) -> int:
        return self.h_template

    def is_h_skip_enabled(self) -> bool:
        return self.h_skip_enabled

    def is_mmr_encoded_flag(self) -> bool:
        return self.is_mmr_encoded

    def get_h_grid_width(self) -> int:
        return self.h_grid_width

    def get_h_grid_height(self) -> int:
        return self.h_grid_height

    def get_h_grid_x(self) -> int:
        return self.h_grid_x

    def get_h_grid_y(self) -> int:
        return self.h_grid_y

    def get_h_region_x(self) -> int:
        return self.h_region_x

    def get_h_region_y(self) -> int:
        return self.h_region_y

    def get_h_default_pixel(self) -> int:
        return self.h_default_pixel

    def _compute_h_skip(self, h_pattern_width: int, h_pattern_height: int) -> Bitmap:
        # 6.6.5.1 Computing HSKIP
        bitmap = Bitmap(self.h_grid_width, self.h_grid_height)  # HSKIP is HGW by HGH
        for m in range(self.h_grid_height):
            for n in range(self.h_grid_width):
                x = self._compute_x(m, n)
                y = self._compute_y(m, n)
                # HBW = halftone_region_bitmap.get_width()
                # HBH = halftone_region_bitmap.get_height()
                if (
                    x + h_pattern_width <= 0
                    or x >= self.halftone_region_bitmap.get_width()
                    or y + h_pattern_height <= 0
                    or y >= self.halftone_region_bitmap.get_height()
                ):
                    bitmap.set_pixel(n, m, 1)
                # else no need to set 0 pixels
        return bitmap
