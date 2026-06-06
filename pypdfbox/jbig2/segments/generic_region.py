"""Generic region segment (JBIG2 §7.4.5 parsing, §6.2.5.7 / §7.4.6.4 decode).

Port of ``org.apache.pdfbox.jbig2.segments.GenericRegion``. Decodes a generic
region either via the MMR (CCITT Group-4) decompressor or via the arithmetic
generic-region procedure (templates 0-3, with TPGDON typical-prediction and AT
adaptive-template pixels).

The GB context register is a Java ``int`` whose low 16 bits drive the
arithmetic context selection. Python ints are unbounded, so the running
``context`` register is masked to 16 bits with ``& 0xFFFF`` exactly where the
context is rebuilt each pixel — the CX array is sized 65536, so only the low 16
bits are ever indexed. The ``line1`` / ``line2`` shift registers are left
unmasked: every read of them extracts a single low bit via ``(line >> n) &
0x..``, so their (unbounded) high bits never reach the result, matching the
upstream where the bits shifted past the high end of the Java ``int`` are
likewise discarded by the same masked extraction. ``read_byte()`` yields a
signed value (-128..127) just like Java's ``short``-promoted ``readByte()``, so
the AT coordinates stay signed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.jbig2.bitmap import Bitmap
from pypdfbox.jbig2.decoder.arithmetic.arithmetic_decoder import ArithmeticDecoder
from pypdfbox.jbig2.decoder.arithmetic.cx import CX
from pypdfbox.jbig2.decoder.mmr.mmr_decompressor import MMRDecompressor
from pypdfbox.jbig2.io.sub_input_stream import SubInputStream
from pypdfbox.jbig2.region import Region
from pypdfbox.jbig2.segments.region_segment_information import RegionSegmentInformation

if TYPE_CHECKING:
    from pypdfbox.jbig2.segment_header import SegmentHeader

_MASK16 = 0xFFFF


def _java_ushr(value: int, shift: int) -> int:
    """Mirror Java's ``int >>`` shift-count semantics for a non-negative byte
    accumulator. Java masks the shift count to its low 5 bits
    (``shift & 0x1F``), so a *negative* shift (which arises in the AT-pixel
    override expressions when ``minor_x + gbAtX`` exceeds 7) becomes a large
    positive shift rather than raising. For the small ``result`` accumulator
    (< 256) every such case yields 0, exactly as upstream PDFBox computes."""
    return value >> (shift & 0x1F)


class GenericRegion(Region):
    """A generic region segment.

    Parsing is done as described in 7.4.5. Decoding procedure is done as
    described in 6.2.5.7 and 7.4.6.4.
    """

    def __init__(self, sub_input_stream: SubInputStream | None = None) -> None:
        self.sub_input_stream = sub_input_stream

        self.data_header_offset = 0
        self.data_header_length = 0
        self.data_offset = 0
        self.data_length = 0

        # Region segment information field, 7.4.1
        if sub_input_stream is not None:
            self.region_info: RegionSegmentInformation | None = (
                RegionSegmentInformation(sub_input_stream)
            )
        else:
            self.region_info = None

        # Generic region segment flags, 7.4.6.2
        self.use_ext_templates = False
        self.is_tpgdon = False
        self.gb_template = 0
        self.is_mmr_encoded = False

        # Generic region segment AT flags, 7.4.6.3
        self.gb_at_x: list[int] | None = None
        self.gb_at_y: list[int] | None = None
        self.gb_at_override: list[bool] | None = None

        # If True, AT pixels are not on their nominal location and have to be
        # overridden.
        self.override = False

        # Decoded data as pixel values (use row stride/width to wrap line).
        self.region_bitmap: Bitmap | None = None

        self.arith_decoder: ArithmeticDecoder | None = None
        self.cx: CX | None = None

        self.mmr_decompressor: MMRDecompressor | None = None

        self.use_skip = False
        self.h_skip: Bitmap | None = None

    def _parse_header(self) -> None:
        self.region_info.parse_header()

        # Bit 5-7
        self.sub_input_stream.read_bits(3)  # Dirty read...

        # Bit 4
        if self.sub_input_stream.read_bit() == 1:
            self.use_ext_templates = True

        # Bit 3
        if self.sub_input_stream.read_bit() == 1:
            self.is_tpgdon = True

        # Bit 1-2
        self.gb_template = self.sub_input_stream.read_bits(2) & 0xF

        # Bit 0
        if self.sub_input_stream.read_bit() == 1:
            self.is_mmr_encoded = True

        if not self.is_mmr_encoded:
            if self.gb_template == 0:  # noqa: SIM108
                amount_of_gb_at = 12 if self.use_ext_templates else 4
            else:
                amount_of_gb_at = 1

            self._read_gb_at_pixels(amount_of_gb_at)

        # Segment data structure
        self._compute_segment_data_structure()

    def _read_gb_at_pixels(self, amount_of_gb_at: int) -> None:
        self.gb_at_x = [0] * amount_of_gb_at
        self.gb_at_y = [0] * amount_of_gb_at

        for i in range(amount_of_gb_at):
            self.gb_at_x[i] = self.sub_input_stream.read_byte()
            self.gb_at_y[i] = self.sub_input_stream.read_byte()

    def _compute_segment_data_structure(self) -> None:
        self.data_offset = self.sub_input_stream.get_stream_position()
        self.data_header_length = self.data_offset - self.data_header_offset
        self.data_length = self.sub_input_stream.length() - self.data_header_length

    def get_region_bitmap(self) -> Bitmap:
        """Decode the region. The procedure is described in 6.2.5.7, page 17."""
        if self.region_bitmap is None:
            if self.is_mmr_encoded:
                # MMR DECODER CALL
                if self.mmr_decompressor is None:
                    self.mmr_decompressor = MMRDecompressor(
                        self.region_info.get_bitmap_width(),
                        self.region_info.get_bitmap_height(),
                        SubInputStream(
                            self.sub_input_stream, self.data_offset, self.data_length
                        ),
                    )

                # 6.2.6
                self.region_bitmap = self.mmr_decompressor.uncompress()
            else:
                # ARITHMETIC DECODER PROCEDURE for generic region segments
                self._update_override_flags()

                # 6.2.5.7 - 1)
                ltp = 0

                if self.arith_decoder is None:
                    self.arith_decoder = ArithmeticDecoder(self.sub_input_stream)
                if self.cx is None:
                    self.cx = CX(65536, 1)

                # 6.2.5.7 - 2)
                self.region_bitmap = Bitmap(
                    self.region_info.get_bitmap_width(),
                    self.region_info.get_bitmap_height(),
                )

                padded_width = (self.region_bitmap.get_width() + 7) & -8

                # 6.2.5.7 - 3
                for line in range(self.region_bitmap.get_height()):
                    # 6.2.5.7 - 3 b)
                    if self.is_tpgdon:
                        ltp ^= self._decode_sltp()

                    # 6.2.5.7 - 3 c)
                    if ltp == 1:
                        if line > 0:
                            self._copy_line_above(line)
                    else:
                        # 6.2.5.7 - 3 d)
                        self._decode_line(
                            line,
                            self.region_bitmap.get_width(),
                            self.region_bitmap.get_row_stride(),
                            padded_width,
                        )

        # 4
        return self.region_bitmap

    def _decode_sltp(self) -> int:
        if self.gb_template == 0:
            self.cx.set_index(0x9B25)
        elif self.gb_template == 1:
            self.cx.set_index(0x795)
        elif self.gb_template == 2:
            self.cx.set_index(0xE5)
        elif self.gb_template == 3:
            self.cx.set_index(0x195)
        return self.arith_decoder.decode(self.cx)

    def _decode_line(
        self, line_number: int, width: int, row_stride: int, padded_width: int
    ) -> None:
        byte_index = self.region_bitmap.get_byte_index(0, line_number)
        idx = byte_index - row_stride

        if self.gb_template == 0:
            if not self.use_ext_templates:
                self._decode_template0a(
                    line_number, width, row_stride, padded_width, byte_index, idx
                )
            else:
                self._decode_template0b(
                    line_number, width, row_stride, padded_width, byte_index, idx
                )
        elif self.gb_template == 1:
            self._decode_template1(
                line_number, width, row_stride, padded_width, byte_index, idx
            )
        elif self.gb_template == 2:
            self._decode_template2(
                line_number, width, row_stride, padded_width, byte_index, idx
            )
        elif self.gb_template == 3:
            self._decode_template3(
                line_number, width, row_stride, padded_width, byte_index, idx
            )

    def _copy_line_above(self, line_number: int) -> None:
        """Copy each pixel from the corresponding pixel of the row above.

        Line 0 cannot get copied values (source would not exist).
        """
        target_byte_index = line_number * self.region_bitmap.get_row_stride()
        source_byte_index = target_byte_index - self.region_bitmap.get_row_stride()

        for _ in range(self.region_bitmap.get_row_stride()):
            self.region_bitmap.set_byte(
                target_byte_index, self.region_bitmap.get_byte(source_byte_index)
            )
            target_byte_index += 1
            source_byte_index += 1

    def _decode_template0a(
        self,
        line_number: int,
        width: int,
        row_stride: int,
        padded_width: int,
        byte_index: int,
        idx: int,
    ) -> None:
        line1 = 0
        line2 = 0

        if line_number >= 1:
            line1 = self.region_bitmap.get_byte_as_integer(idx)

        if line_number >= 2:
            line2 = self.region_bitmap.get_byte_as_integer(idx - row_stride) << 6

        context = (line1 & 0xF0) | (line2 & 0x3800)

        x = 0
        while x < padded_width:
            # 6.2.5.7 3d
            result = 0
            next_byte = x + 8
            minor_width = 8 if width - x > 8 else width - x

            if line_number > 0:
                line1 = (line1 << 8) | (
                    self.region_bitmap.get_byte_as_integer(idx + 1)
                    if next_byte < width
                    else 0
                )

            if line_number > 1:
                line2 = (line2 << 8) | (
                    self.region_bitmap.get_byte_as_integer(idx - row_stride + 1) << 6
                    if next_byte < width
                    else 0
                )

            for minor_x in range(minor_width):
                to_shift = 7 - minor_x
                if self.override:
                    overridden_context = self._override_at_template0a(
                        context, x + minor_x, line_number, result, minor_x, to_shift
                    )
                    self.cx.set_index(overridden_context)
                else:
                    self.cx.set_index(context)

                if self.use_skip and self.h_skip.get_pixel(x + minor_x, line_number) == 1:
                    bit = 0
                else:
                    bit = self.arith_decoder.decode(self.cx)

                result |= bit << to_shift

                context = (
                    ((context & 0x7BF7) << 1)
                    | bit
                    | ((line1 >> to_shift) & 0x10)
                    | ((line2 >> to_shift) & 0x800)
                ) & _MASK16

            self.region_bitmap.set_byte(byte_index, result)
            byte_index += 1
            idx += 1
            x = next_byte

    def _decode_template0b(
        self,
        line_number: int,
        width: int,
        row_stride: int,
        padded_width: int,
        byte_index: int,
        idx: int,
    ) -> None:
        line1 = 0
        line2 = 0

        if line_number >= 1:
            line1 = self.region_bitmap.get_byte_as_integer(idx)

        if line_number >= 2:
            line2 = self.region_bitmap.get_byte_as_integer(idx - row_stride) << 6

        context = (line1 & 0xF0) | (line2 & 0x3800)

        x = 0
        while x < padded_width:
            # 6.2.5.7 3d
            result = 0
            next_byte = x + 8
            minor_width = 8 if width - x > 8 else width - x

            if line_number > 0:
                line1 = (line1 << 8) | (
                    self.region_bitmap.get_byte_as_integer(idx + 1)
                    if next_byte < width
                    else 0
                )

            if line_number > 1:
                line2 = (line2 << 8) | (
                    self.region_bitmap.get_byte_as_integer(idx - row_stride + 1) << 6
                    if next_byte < width
                    else 0
                )

            for minor_x in range(minor_width):
                to_shift = 7 - minor_x
                if self.override:
                    overridden_context = self._override_at_template0b(
                        context, x + minor_x, line_number, result, minor_x, to_shift
                    )
                    self.cx.set_index(overridden_context)
                else:
                    self.cx.set_index(context)

                if self.use_skip and self.h_skip.get_pixel(x + minor_x, line_number) == 1:
                    bit = 0
                else:
                    bit = self.arith_decoder.decode(self.cx)

                result |= bit << to_shift

                context = (
                    ((context & 0x7BF7) << 1)
                    | bit
                    | ((line1 >> to_shift) & 0x10)
                    | ((line2 >> to_shift) & 0x800)
                ) & _MASK16

            self.region_bitmap.set_byte(byte_index, result)
            byte_index += 1
            idx += 1
            x = next_byte

    def _decode_template1(
        self,
        line_number: int,
        width: int,
        row_stride: int,
        padded_width: int,
        byte_index: int,
        idx: int,
    ) -> None:
        line1 = 0
        line2 = 0

        if line_number >= 1:
            line1 = self.region_bitmap.get_byte_as_integer(idx)

        if line_number >= 2:
            line2 = self.region_bitmap.get_byte_as_integer(idx - row_stride) << 5

        context = ((line1 >> 1) & 0x1F8) | ((line2 >> 1) & 0x1E00)

        x = 0
        while x < padded_width:
            # 6.2.5.7 3d
            result = 0
            next_byte = x + 8
            minor_width = 8 if width - x > 8 else width - x

            if line_number >= 1:
                line1 = (line1 << 8) | (
                    self.region_bitmap.get_byte_as_integer(idx + 1)
                    if next_byte < width
                    else 0
                )

            if line_number >= 2:
                line2 = (line2 << 8) | (
                    self.region_bitmap.get_byte_as_integer(idx - row_stride + 1) << 5
                    if next_byte < width
                    else 0
                )

            for minor_x in range(minor_width):
                if self.override:
                    overridden_context = self._override_at_template1(
                        context, x + minor_x, line_number, result, minor_x
                    )
                    self.cx.set_index(overridden_context)
                else:
                    self.cx.set_index(context)

                if self.use_skip and self.h_skip.get_pixel(x + minor_x, line_number) == 1:
                    bit = 0
                else:
                    bit = self.arith_decoder.decode(self.cx)

                result |= bit << (7 - minor_x)

                to_shift = 8 - minor_x
                context = (
                    ((context & 0xEFB) << 1)
                    | bit
                    | ((line1 >> to_shift) & 0x8)
                    | ((line2 >> to_shift) & 0x200)
                ) & _MASK16

            self.region_bitmap.set_byte(byte_index, result)
            byte_index += 1
            idx += 1
            x = next_byte

    def _decode_template2(
        self,
        line_number: int,
        width: int,
        row_stride: int,
        padded_width: int,
        byte_index: int,
        idx: int,
    ) -> None:
        line1 = 0
        line2 = 0

        if line_number >= 1:
            line1 = self.region_bitmap.get_byte_as_integer(idx)

        if line_number >= 2:
            line2 = self.region_bitmap.get_byte_as_integer(idx - row_stride) << 4

        context = ((line1 >> 3) & 0x7C) | ((line2 >> 3) & 0x380)

        x = 0
        while x < padded_width:
            # 6.2.5.7 3d
            result = 0
            next_byte = x + 8
            minor_width = 8 if width - x > 8 else width - x

            if line_number >= 1:
                line1 = (line1 << 8) | (
                    self.region_bitmap.get_byte_as_integer(idx + 1)
                    if next_byte < width
                    else 0
                )

            if line_number >= 2:
                line2 = (line2 << 8) | (
                    self.region_bitmap.get_byte_as_integer(idx - row_stride + 1) << 4
                    if next_byte < width
                    else 0
                )

            for minor_x in range(minor_width):
                if self.override:
                    overridden_context = self._override_at_template2(
                        context, x + minor_x, line_number, result, minor_x
                    )
                    self.cx.set_index(overridden_context)
                else:
                    self.cx.set_index(context)

                if self.use_skip and self.h_skip.get_pixel(x + minor_x, line_number) == 1:
                    bit = 0
                else:
                    bit = self.arith_decoder.decode(self.cx)

                result |= bit << (7 - minor_x)

                to_shift = 10 - minor_x
                context = (
                    ((context & 0x1BD) << 1)
                    | bit
                    | ((line1 >> to_shift) & 0x4)
                    | ((line2 >> to_shift) & 0x80)
                ) & _MASK16

            self.region_bitmap.set_byte(byte_index, result)
            byte_index += 1
            idx += 1
            x = next_byte

    def _decode_template3(
        self,
        line_number: int,
        width: int,
        row_stride: int,
        padded_width: int,
        byte_index: int,
        idx: int,
    ) -> None:
        line1 = 0

        if line_number >= 1:
            line1 = self.region_bitmap.get_byte_as_integer(idx)

        context = (line1 >> 1) & 0x70

        x = 0
        while x < padded_width:
            # 6.2.5.7 3d
            result = 0
            next_byte = x + 8
            minor_width = 8 if width - x > 8 else width - x

            if line_number >= 1:
                line1 = (line1 << 8) | (
                    self.region_bitmap.get_byte_as_integer(idx + 1)
                    if next_byte < width
                    else 0
                )

            for minor_x in range(minor_width):
                if self.override:
                    overridden_context = self._override_at_template3(
                        context, x + minor_x, line_number, result, minor_x
                    )
                    self.cx.set_index(overridden_context)
                else:
                    self.cx.set_index(context)

                if self.use_skip and self.h_skip.get_pixel(x + minor_x, line_number) == 1:
                    bit = 0
                else:
                    bit = self.arith_decoder.decode(self.cx)

                result |= bit << (7 - minor_x)
                context = (
                    ((context & 0x1F7) << 1)
                    | bit
                    | ((line1 >> (8 - minor_x)) & 0x010)
                ) & _MASK16

            self.region_bitmap.set_byte(byte_index, result)
            byte_index += 1
            idx += 1
            x = next_byte

    def _update_override_flags(self) -> None:
        if self.gb_at_x is None or self.gb_at_y is None:
            return

        if len(self.gb_at_x) != len(self.gb_at_y):
            return

        self.gb_at_override = [False] * len(self.gb_at_x)

        if self.gb_template == 0:
            if not self.use_ext_templates:
                if self.gb_at_x[0] != 3 or self.gb_at_y[0] != -1:
                    self._set_override_flag(0)
                if self.gb_at_x[1] != -3 or self.gb_at_y[1] != -1:
                    self._set_override_flag(1)
                if self.gb_at_x[2] != 2 or self.gb_at_y[2] != -2:
                    self._set_override_flag(2)
                if self.gb_at_x[3] != -2 or self.gb_at_y[3] != -2:
                    self._set_override_flag(3)
            else:
                if self.gb_at_x[0] != -2 or self.gb_at_y[0] != 0:
                    self._set_override_flag(0)
                if self.gb_at_x[1] != 0 or self.gb_at_y[1] != -2:
                    self._set_override_flag(1)
                if self.gb_at_x[2] != -2 or self.gb_at_y[2] != -1:
                    self._set_override_flag(2)
                if self.gb_at_x[3] != -1 or self.gb_at_y[3] != -2:
                    self._set_override_flag(3)
                if self.gb_at_x[4] != 1 or self.gb_at_y[4] != -2:
                    self._set_override_flag(4)
                if self.gb_at_x[5] != 2 or self.gb_at_y[5] != -1:
                    self._set_override_flag(5)
                if self.gb_at_x[6] != -3 or self.gb_at_y[6] != 0:
                    self._set_override_flag(6)
                if self.gb_at_x[7] != -4 or self.gb_at_y[7] != 0:
                    self._set_override_flag(7)
                if self.gb_at_x[8] != 2 or self.gb_at_y[8] != -2:
                    self._set_override_flag(8)
                if self.gb_at_x[9] != 3 or self.gb_at_y[9] != -1:
                    self._set_override_flag(9)
                if self.gb_at_x[10] != -2 or self.gb_at_y[10] != -2:
                    self._set_override_flag(10)
                if self.gb_at_x[11] != -3 or self.gb_at_y[11] != -1:
                    self._set_override_flag(11)
        elif self.gb_template == 1:
            if self.gb_at_x[0] != 3 or self.gb_at_y[0] != -1:
                self._set_override_flag(0)
        elif self.gb_template in (2, 3):  # noqa: SIM102
            if self.gb_at_x[0] != 2 or self.gb_at_y[0] != -1:
                self._set_override_flag(0)

    def _set_override_flag(self, index: int) -> None:
        self.gb_at_override[index] = True
        self.override = True

    def _override_at_template0a(
        self,
        context: int,
        x: int,
        y: int,
        result: int,
        minor_x: int,
        to_shift: int,
    ) -> int:
        if self.gb_at_override[0]:
            context &= 0xFFEF
            if self.gb_at_y[0] == 0 and self.gb_at_x[0] >= -minor_x:
                context |= (_java_ushr(result, to_shift - self.gb_at_x[0]) & 0x1) << 4
            else:
                context |= self._get_pixel_safe(x + self.gb_at_x[0], y + self.gb_at_y[0]) << 4

        if self.gb_at_override[1]:
            context &= 0xFBFF
            if self.gb_at_y[1] == 0 and self.gb_at_x[1] >= -minor_x:
                context |= (_java_ushr(result, to_shift - self.gb_at_x[1]) & 0x1) << 10
            else:
                context |= self._get_pixel_safe(x + self.gb_at_x[1], y + self.gb_at_y[1]) << 10

        if self.gb_at_override[2]:
            context &= 0xF7FF
            if self.gb_at_y[2] == 0 and self.gb_at_x[2] >= -minor_x:
                context |= (_java_ushr(result, to_shift - self.gb_at_x[2]) & 0x1) << 11
            else:
                context |= self._get_pixel_safe(x + self.gb_at_x[2], y + self.gb_at_y[2]) << 11

        if self.gb_at_override[3]:
            context &= 0x7FFF
            if self.gb_at_y[3] == 0 and self.gb_at_x[3] >= -minor_x:
                context |= (_java_ushr(result, to_shift - self.gb_at_x[3]) & 0x1) << 15
            else:
                context |= self._get_pixel_safe(x + self.gb_at_x[3], y + self.gb_at_y[3]) << 15
        return context & _MASK16

    def _override_at_template0b(
        self,
        context: int,
        x: int,
        y: int,
        result: int,
        minor_x: int,
        to_shift: int,
    ) -> int:
        if self.gb_at_override[0]:
            context &= 0xFFFD
            if self.gb_at_y[0] == 0 and self.gb_at_x[0] >= -minor_x:
                context |= (_java_ushr(result, to_shift - self.gb_at_x[0]) & 0x1) << 1
            else:
                context |= self._get_pixel_safe(x + self.gb_at_x[0], y + self.gb_at_y[0]) << 1

        if self.gb_at_override[1]:
            context &= 0xDFFF
            if self.gb_at_y[1] == 0 and self.gb_at_x[1] >= -minor_x:
                context |= (_java_ushr(result, to_shift - self.gb_at_x[1]) & 0x1) << 13
            else:
                context |= self._get_pixel_safe(x + self.gb_at_x[1], y + self.gb_at_y[1]) << 13
        if self.gb_at_override[2]:
            context &= 0xFDFF
            if self.gb_at_y[2] == 0 and self.gb_at_x[2] >= -minor_x:
                context |= (_java_ushr(result, to_shift - self.gb_at_x[2]) & 0x1) << 9
            else:
                context |= self._get_pixel_safe(x + self.gb_at_x[2], y + self.gb_at_y[2]) << 9
        if self.gb_at_override[3]:
            context &= 0xBFFF
            if self.gb_at_y[3] == 0 and self.gb_at_x[3] >= -minor_x:
                context |= (_java_ushr(result, to_shift - self.gb_at_x[3]) & 0x1) << 14
            else:
                context |= self._get_pixel_safe(x + self.gb_at_x[3], y + self.gb_at_y[3]) << 14
        if self.gb_at_override[4]:
            context &= 0xEFFF
            if self.gb_at_y[4] == 0 and self.gb_at_x[4] >= -minor_x:
                context |= (_java_ushr(result, to_shift - self.gb_at_x[4]) & 0x1) << 12
            else:
                context |= self._get_pixel_safe(x + self.gb_at_x[4], y + self.gb_at_y[4]) << 12
        if self.gb_at_override[5]:
            context &= 0xFFDF
            if self.gb_at_y[5] == 0 and self.gb_at_x[5] >= -minor_x:
                context |= (_java_ushr(result, to_shift - self.gb_at_x[5]) & 0x1) << 5
            else:
                context |= self._get_pixel_safe(x + self.gb_at_x[5], y + self.gb_at_y[5]) << 5
        if self.gb_at_override[6]:
            context &= 0xFFFB
            if self.gb_at_y[6] == 0 and self.gb_at_x[6] >= -minor_x:
                context |= (_java_ushr(result, to_shift - self.gb_at_x[6]) & 0x1) << 2
            else:
                context |= self._get_pixel_safe(x + self.gb_at_x[6], y + self.gb_at_y[6]) << 2
        if self.gb_at_override[7]:
            context &= 0xFFF7
            if self.gb_at_y[7] == 0 and self.gb_at_x[7] >= -minor_x:
                context |= (_java_ushr(result, to_shift - self.gb_at_x[7]) & 0x1) << 3
            else:
                context |= self._get_pixel_safe(x + self.gb_at_x[7], y + self.gb_at_y[7]) << 3
        if self.gb_at_override[8]:
            context &= 0xF7FF
            if self.gb_at_y[8] == 0 and self.gb_at_x[8] >= -minor_x:
                context |= (_java_ushr(result, to_shift - self.gb_at_x[8]) & 0x1) << 11
            else:
                context |= self._get_pixel_safe(x + self.gb_at_x[8], y + self.gb_at_y[8]) << 11
        if self.gb_at_override[9]:
            context &= 0xFFEF
            if self.gb_at_y[9] == 0 and self.gb_at_x[9] >= -minor_x:
                context |= (_java_ushr(result, to_shift - self.gb_at_x[9]) & 0x1) << 4
            else:
                context |= self._get_pixel_safe(x + self.gb_at_x[9], y + self.gb_at_y[9]) << 4
        if self.gb_at_override[10]:
            context &= 0x7FFF
            if self.gb_at_y[10] == 0 and self.gb_at_x[10] >= -minor_x:
                context |= (_java_ushr(result, to_shift - self.gb_at_x[10]) & 0x1) << 15
            else:
                context |= self._get_pixel_safe(x + self.gb_at_x[10], y + self.gb_at_y[10]) << 15
        if self.gb_at_override[11]:
            context &= 0xFDFF
            if self.gb_at_y[11] == 0 and self.gb_at_x[11] >= -minor_x:
                context |= (_java_ushr(result, to_shift - self.gb_at_x[11]) & 0x1) << 10
            else:
                context |= self._get_pixel_safe(x + self.gb_at_x[11], y + self.gb_at_y[11]) << 10

        return context & _MASK16

    def _override_at_template1(
        self, context: int, x: int, y: int, result: int, minor_x: int
    ) -> int:
        context &= 0x1FF7
        if self.gb_at_y[0] == 0 and self.gb_at_x[0] >= -minor_x:
            return (
                context | (_java_ushr(result, 7 - (minor_x + self.gb_at_x[0])) & 0x1) << 3
            ) & _MASK16
        else:
            return (
                context | self._get_pixel_safe(x + self.gb_at_x[0], y + self.gb_at_y[0]) << 3
            ) & _MASK16

    def _override_at_template2(
        self, context: int, x: int, y: int, result: int, minor_x: int
    ) -> int:
        context &= 0x3FB
        if self.gb_at_y[0] == 0 and self.gb_at_x[0] >= -minor_x:
            return (
                context | (_java_ushr(result, 7 - (minor_x + self.gb_at_x[0])) & 0x1) << 2
            ) & _MASK16
        else:
            return (
                context | self._get_pixel_safe(x + self.gb_at_x[0], y + self.gb_at_y[0]) << 2
            ) & _MASK16

    def _override_at_template3(
        self, context: int, x: int, y: int, result: int, minor_x: int
    ) -> int:
        context &= 0x3EF
        if self.gb_at_y[0] == 0 and self.gb_at_x[0] >= -minor_x:
            return (
                context | (_java_ushr(result, 7 - (minor_x + self.gb_at_x[0])) & 0x1) << 4
            ) & _MASK16
        else:
            return (
                context | self._get_pixel_safe(x + self.gb_at_x[0], y + self.gb_at_y[0]) << 4
            ) & _MASK16

    def _get_pixel_safe(self, x: int, y: int) -> int:
        if x < 0 or x >= self.region_bitmap.get_width():
            return 0

        if y < 0 or y >= self.region_bitmap.get_height():
            return 0

        return self.region_bitmap.get_pixel(x, y)

    def set_parameters(
        self,
        is_mmr_encoded: bool,
        data_offset: int | None = None,
        data_length: int | None = None,
        gbh: int | None = None,
        gbw: int | None = None,
        gb_template: int | None = None,
        is_tpgdon: bool | None = None,
        use_skip: bool | None = None,
        h_skip: Bitmap | None = None,
        gb_at_x: list[int] | None = None,
        gb_at_y: list[int] | None = None,
        *,
        sd_template: int | None = None,
        sym_width: int | None = None,
        hc_height: int | None = None,
        cx: CX | None = None,
        arithmetic_decoder: ArithmeticDecoder | None = None,
        variant: str | None = None,
    ) -> None:
        """Configure this region's parameters externally.

        Mirrors the three overloaded ``setParameters`` upstream:

        * ``"dict_simple"`` — used by ``SymbolDictionary`` (height/width only).
        * ``"dict_full"`` — used by ``SymbolDictionary`` (template + AT + cx +
          decoder, supplying ``sd_template``, ``sym_width``, ``hc_height``).
        * ``"pattern"`` (default when ``cx`` / ``sd_template`` are absent) — used
          by ``PatternDictionary`` and ``HalftoneRegion``.

        The ``variant`` keyword disambiguates the simple-dictionary overload
        (which shares its positional signature prefix with the pattern one).
        """
        if sd_template is not None or arithmetic_decoder is not None or cx is not None:
            # SymbolDictionary full overload.
            self.is_mmr_encoded = is_mmr_encoded
            self.gb_template = sd_template if sd_template is not None else gb_template
            self.is_tpgdon = is_tpgdon
            self.gb_at_x = gb_at_x
            self.gb_at_y = gb_at_y
            self.region_info.set_bitmap_width(sym_width)
            self.region_info.set_bitmap_height(hc_height)
            if cx is not None:
                self.cx = cx
            if arithmetic_decoder is not None:
                self.arith_decoder = arithmetic_decoder
            self.mmr_decompressor = None
            self.use_skip = use_skip
            self.reset_bitmap()
        elif variant == "dict_simple" or (
            gb_template is None and is_tpgdon is None and use_skip is None
        ):
            # SymbolDictionary simple overload (height/width only).
            self.is_mmr_encoded = is_mmr_encoded
            self.data_offset = data_offset
            self.data_length = data_length
            self.region_info.set_bitmap_height(gbh)
            self.region_info.set_bitmap_width(gbw)
            self.mmr_decompressor = None
            self.reset_bitmap()
        else:
            # PatternDictionary / HalftoneRegion overload.
            self.data_offset = data_offset
            self.data_length = data_length
            self.region_info = RegionSegmentInformation()
            self.region_info.set_bitmap_height(gbh)
            self.region_info.set_bitmap_width(gbw)
            self.gb_template = gb_template
            self.is_mmr_encoded = is_mmr_encoded
            self.is_tpgdon = is_tpgdon
            self.gb_at_x = gb_at_x
            self.gb_at_y = gb_at_y
            self.use_skip = use_skip
            self.h_skip = h_skip

    def reset_bitmap(self) -> None:
        """Set the memory-critical bitmap of this region to ``None``."""
        self.region_bitmap = None

    def init(self, header: SegmentHeader, sis: SubInputStream) -> None:
        self.sub_input_stream = sis
        self.region_info = RegionSegmentInformation(self.sub_input_stream)
        self._parse_header()

    def get_region_info(self) -> RegionSegmentInformation:
        return self.region_info

    def use_ext_templates_flag(self) -> bool:
        return self.use_ext_templates

    def is_tpgdon_flag(self) -> bool:
        return self.is_tpgdon

    def get_gb_template(self) -> int:
        return self.gb_template

    def is_mmr_encoded_flag(self) -> bool:
        return self.is_mmr_encoded

    def get_gb_at_x(self) -> list[int] | None:
        return self.gb_at_x

    def get_gb_at_y(self) -> list[int] | None:
        return self.gb_at_y
