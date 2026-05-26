from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.jbig2.dictionary import Dictionary
from pypdfbox.jbig2.err.invalid_header_value_exception import (
    InvalidHeaderValueException,
)
from pypdfbox.jbig2.image.bitmaps import Bitmaps
from pypdfbox.jbig2.segments.generic_region import GenericRegion

if TYPE_CHECKING:
    from pypdfbox.jbig2.bitmap import Bitmap
    from pypdfbox.jbig2.io.sub_input_stream import SubInputStream
    from pypdfbox.jbig2.segment_header import SegmentHeader


class PatternDictionary(Dictionary):
    """The segment type "Pattern dictionary", 7.4.4.

    Mirrors ``org.apache.pdfbox.jbig2.segments.PatternDictionary``.
    """

    def __init__(self) -> None:
        self.sub_input_stream: SubInputStream | None = None

        # Segment data structure (only necessary if MMR is used).
        self.data_header_offset = 0
        self.data_header_length = 0
        self.data_offset = 0
        self.data_length = 0

        self.gb_at_x: list[int] | None = None
        self.gb_at_y: list[int] | None = None

        # Pattern dictionary flags, 7.4.4.1.1
        self.is_mmr_encoded = False
        self.hd_template = 0

        # Width of the patterns in the pattern dictionary, 7.4.4.1.2
        self.hdp_width = 0
        # Height of the patterns in the pattern dictionary, 7.4.4.1.3
        self.hdp_height = 0

        # Decoded bitmaps, stored to be used by segments that refer to it.
        self.patterns: list[Bitmap] | None = None

        # Largest gray-scale value, 7.4.4.1.4. Value: one less than the number
        # of patterns defined in this pattern dictionary.
        self.gray_max = 0

    def _parse_header(self) -> None:
        # Bit 3-7
        self.sub_input_stream.read_bits(5)  # Dirty read...

        # Bit 1-2
        self._read_template()

        # Bit 0
        self._read_is_mmr_encoded()

        self._read_pattern_width_and_height()

        self._read_gray_max()

        # Segment data structure
        self._compute_segment_data_structure()

        self._check_input()

    def _read_template(self) -> None:
        # Bit 1-2
        self.hd_template = int(self.sub_input_stream.read_bits(2))

    def _read_is_mmr_encoded(self) -> None:
        # Bit 0
        if self.sub_input_stream.read_bit() == 1:
            self.is_mmr_encoded = True

    def _read_pattern_width_and_height(self) -> None:
        self.hdp_width = self.sub_input_stream.read_byte() & 0xFF
        self.hdp_height = self.sub_input_stream.read_byte() & 0xFF

    def _read_gray_max(self) -> None:
        self.gray_max = int(self.sub_input_stream.read_bits(32) & 0xFFFFFFFF)

    def _compute_segment_data_structure(self) -> None:
        self.data_offset = self.sub_input_stream.get_stream_position()
        self.data_header_length = self.data_offset - self.data_header_offset
        self.data_length = self.sub_input_stream.length() - self.data_header_length

    def _check_input(self) -> None:
        if self.hdp_height < 1 or self.hdp_width < 1:
            raise InvalidHeaderValueException(
                "Width/Heigth must be greater than zero."
            )

    def get_dictionary(self) -> list[Bitmap]:
        """Decode a pattern dictionary segment and return a list of patterns.

        Each of the returned :class:`Bitmap`\\ s is a pattern. The procedure is
        described in 6.7.5 (page 43).

        :return: A list of :class:`Bitmap`\\ s as result of the decoding
            procedure.
        """
        if self.patterns is None:
            if not self.is_mmr_encoded:
                self._set_gb_at_pixels()

            # 2)
            generic_region = GenericRegion(self.sub_input_stream)
            generic_region.set_parameters(
                self.is_mmr_encoded,
                self.data_offset,
                self.data_length,
                self.hdp_height,
                (self.gray_max + 1) * self.hdp_width,
                self.hd_template,
                False,
                False,
                None,
                self.gb_at_x,
                self.gb_at_y,
            )

            collective_bitmap = generic_region.get_region_bitmap()

            # 4)
            self._extract_patterns(collective_bitmap)

        return self.patterns

    def _extract_patterns(self, collective_bitmap: Bitmap) -> None:
        # 3)
        gray = 0
        self.patterns = []

        # 4)
        while gray <= self.gray_max:
            # 4) a) Retrieve a pattern bitmap by extracting it out of the
            # collective bitmap.
            roi = (self.hdp_width * gray, 0, self.hdp_width, self.hdp_height)
            pattern_bitmap = Bitmaps.extract(roi, collective_bitmap)
            self.patterns.append(pattern_bitmap)

            # 4) b)
            gray += 1

    def _set_gb_at_pixels(self) -> None:
        if self.hd_template == 0:
            self.gb_at_x = [0, 0, 0, 0]
            self.gb_at_y = [0, 0, 0, 0]
            self.gb_at_x[0] = -self.hdp_width
            self.gb_at_y[0] = 0
            self.gb_at_x[1] = -3
            self.gb_at_y[1] = -1
            self.gb_at_x[2] = 2
            self.gb_at_y[2] = -2
            self.gb_at_x[3] = -2
            self.gb_at_y[3] = -2
        else:
            self.gb_at_x = [-self.hdp_width]
            self.gb_at_y = [0]

    def init(self, header: SegmentHeader, sis: SubInputStream) -> None:
        self.sub_input_stream = sis
        self._parse_header()

    def is_mmr_encoded_flag(self) -> bool:
        return self.is_mmr_encoded

    def get_hd_template(self) -> int:
        return self.hd_template

    def get_hdp_width(self) -> int:
        return self.hdp_width

    def get_hdp_height(self) -> int:
        return self.hdp_height

    def get_gray_max(self) -> int:
        return self.gray_max
