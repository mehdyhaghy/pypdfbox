"""Generic region segment (JBIG2 §7.4.5 parsing, §6.2.5.7 / §7.4.6.4 decode).

Port of ``org.apache.pdfbox.jbig2.segments.GenericRegion``. Decodes a generic
region either via the MMR (CCITT Group-4) decompressor or via the arithmetic
generic-region procedure (templates 0-3, with TPGDON typical-prediction and AT
adaptive-template pixels).

The GB context register is a Java ``int`` whose low 16 bits drive the
arithmetic context selection. Python ints are unbounded, so the running
``context`` register is masked to 16 bits with ``& 0xFFFF`` exactly where the
context is rebuilt each pixel — the CX array is sized 65536, so only the low 16
bits are ever indexed. The ``line1`` / ``line2`` shift registers are truncated
to 32 bits like the Java ``int`` registers; every read of them extracts a
single bit no higher than bit 18 via ``(line >> n) & 0x..``, so the discarded
high bits never reach the result. ``read_byte()`` yields a
signed value (-128..127) just like Java's ``short``-promoted ``readByte()``, so
the AT coordinates stay signed.
"""

from typing import TYPE_CHECKING

from pypdfbox.jbig2.bitmap import Bitmap
from pypdfbox.jbig2.decoder.arithmetic.arithmetic_decoder import (
    QE_DECODE,
    RENORM_SHIFTS,
    ArithmeticDecoder,
)
from pypdfbox.jbig2.decoder.arithmetic.cx import CX
from pypdfbox.jbig2.decoder.mmr.mmr_decompressor import MMRDecompressor
from pypdfbox.jbig2.io.sub_input_stream import SubInputStream
from pypdfbox.jbig2.region import Region
from pypdfbox.jbig2.segments.region_segment_information import RegionSegmentInformation

if TYPE_CHECKING:
    from pypdfbox.jbig2.segment_header import SegmentHeader

_MASK16 = 0xFFFF
_MASK32 = 0xFFFFFFFF


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

                params = self._template_params()
                if params is not None:
                    # 6.2.5.7 - 3, all lines in one pass (see _decode_lines_arith)
                    self._decode_lines_arith(
                        0, self.region_bitmap.get_height(), self.is_tpgdon, params
                    )
                else:
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
        row_stride = self.region_bitmap.get_row_stride()
        target_byte_index = line_number * row_stride
        source_byte_index = target_byte_index - row_stride
        data = self.region_bitmap.bitmap_bytes
        data[target_byte_index : target_byte_index + row_stride] = data[
            source_byte_index : source_byte_index + row_stride
        ]

    def _decode_template0a(
        self,
        line_number: int,
        width: int,
        row_stride: int,
        padded_width: int,
        byte_index: int,
        idx: int,
    ) -> None:
        self._decode_lines_arith(
            line_number, line_number + 1, False, self._template_params(0, False)
        )

    def _decode_template0b(
        self,
        line_number: int,
        width: int,
        row_stride: int,
        padded_width: int,
        byte_index: int,
        idx: int,
    ) -> None:
        self._decode_lines_arith(
            line_number, line_number + 1, False, self._template_params(0, True)
        )

    def _decode_template1(
        self,
        line_number: int,
        width: int,
        row_stride: int,
        padded_width: int,
        byte_index: int,
        idx: int,
    ) -> None:
        self._decode_lines_arith(
            line_number, line_number + 1, False, self._template_params(1)
        )

    def _decode_template2(
        self,
        line_number: int,
        width: int,
        row_stride: int,
        padded_width: int,
        byte_index: int,
        idx: int,
    ) -> None:
        self._decode_lines_arith(
            line_number, line_number + 1, False, self._template_params(2)
        )

    def _decode_template3(
        self,
        line_number: int,
        width: int,
        row_stride: int,
        padded_width: int,
        byte_index: int,
        idx: int,
    ) -> None:
        self._decode_lines_arith(
            line_number, line_number + 1, False, self._template_params(3)
        )

    def _template_params(
        self, gb_template: int | None = None, use_ext_templates: bool | None = None
    ) -> tuple | None:
        """Return the per-template constants of the 6.2.5.7 3d line loop.

        ``(line2_shift, init_shift, init_mask1, init_mask2, context_mask,
        context_base_shift, line1_bit, line2_bit, override_at)``: the initial
        context of a line is ``((line1 >> init_shift) & init_mask1) | ((line2
        >> init_shift) & init_mask2)``, and after each pixel it becomes
        ``(((context & context_mask) << 1) | bit | ((line1 >> s) & line1_bit)
        | ((line2 >> s) & line2_bit))`` with ``s = context_base_shift -
        minor_x``. These reproduce the upstream ``decodeTemplate0a`` ..
        ``decodeTemplate3`` expressions exactly. ``override_at`` is the AT
        override hook (``None`` when the AT pixels are nominal). A
        ``line2_shift`` of ``-1`` means the template has no second line.
        Returns ``None`` for a template value outside 0-3.
        """
        if gb_template is None:
            gb_template = self.gb_template
        if use_ext_templates is None:
            use_ext_templates = self.use_ext_templates
        override = self.override
        if gb_template == 0:
            if not use_ext_templates:
                override_at = self._override_at_template0a if override else None
            else:
                override_at = self._override_at_template0b if override else None
            return (6, 0, 0xF0, 0x3800, 0x7BF7, 7, 0x10, 0x800, override_at)

        override_at = None
        if gb_template == 1:
            if override:
                override_t1 = self._override_at_template1

                def override_at(context, x, y, result, minor_x, _to_shift):
                    return override_t1(context, x, y, result, minor_x)

            return (5, 1, 0x1F8, 0x1E00, 0xEFB, 8, 0x8, 0x200, override_at)
        if gb_template == 2:
            if override:
                override_t2 = self._override_at_template2

                def override_at(context, x, y, result, minor_x, _to_shift):
                    return override_t2(context, x, y, result, minor_x)

            return (4, 3, 0x7C, 0x380, 0x1BD, 10, 0x4, 0x80, override_at)
        if gb_template == 3:
            if override:
                override_t3 = self._override_at_template3

                def override_at(context, x, y, result, minor_x, _to_shift):
                    return override_t3(context, x, y, result, minor_x)

            return (-1, 1, 0x70, 0, 0x1F7, 8, 0x010, 0, override_at)
        return None

    def _decode_lines_arith(
        self, first_line: int, end_line: int, is_tpgdon: bool, params: tuple
    ) -> None:
        """Decode lines ``first_line`` .. ``end_line - 1`` (6.2.5.7 3b-3d).

        With ``is_tpgdon`` each line first decodes its SLTP bit and toggles
        LTP (starting from 0 at ``first_line``); a typical line is copied from
        the line above. Otherwise the line is decoded pixel by pixel with the
        template constants from :meth:`_template_params`.

        The MQ ``DECODE`` procedure of :meth:`ArithmeticDecoder.decode` is
        inlined with the decoder registers held in locals, and the bitmap
        bytes are read and written directly; the arithmetic, the context
        formation and the order of decoder calls are unchanged. The
        ``line1`` / ``line2`` registers are truncated to 32 bits like the
        upstream Java ``int`` registers; only their low 19 bits are read.
        """
        (
            line2_shift,
            init_shift,
            init_mask1,
            init_mask2,
            context_mask,
            context_base_shift,
            line1_bit,
            line2_bit,
            override_at,
        ) = params

        bitmap = self.region_bitmap
        data = bitmap.bitmap_bytes
        width = bitmap.width
        row_stride = bitmap.row_stride
        padded_width = (width + 7) & -8
        dec = self.arith_decoder
        cx = self.cx
        qe_table = QE_DECODE
        renorm_shifts = RENORM_SHIFTS

        use_skip = self.use_skip
        skip_bytes = None
        skip_stride = 0
        if use_skip:
            skip_bytes = self.h_skip.bitmap_bytes
            skip_stride = self.h_skip.row_stride
        # The inlined DECODE needs the concrete decoder / context classes and
        # covers the nominal-AT, no-skip case; everything else decodes pixel by
        # pixel through ``decoder.decode``.
        fast = (
            override_at is None
            and not use_skip
            and type(dec) is ArithmeticDecoder
            and type(cx) is CX
        )
        cx_arr = cx._cx if fast else None
        mps_arr = cx._mps if fast else None
        a = c = ct = 0
        index = 0

        sltp_context = (0x9B25, 0x795, 0xE5, 0x195)[self.gb_template] if is_tpgdon else 0
        # (to_shift, s) per pixel position within a byte, and s alone.
        shifts = tuple((7 - m, context_base_shift - m) for m in range(8))
        context_shifts = tuple(context_base_shift - m for m in range(8))

        ltp = 0
        for line_number in range(first_line, end_line):
            # 6.2.5.7 - 3 b)
            if is_tpgdon:
                cx.set_index(sltp_context)
                ltp ^= dec.decode(cx)

            byte_index = line_number * row_stride

            # 6.2.5.7 - 3 c)
            if ltp == 1:
                if line_number > 0:
                    data[byte_index : byte_index + row_stride] = data[
                        byte_index - row_stride : byte_index
                    ]
                continue

            # 6.2.5.7 - 3 d)
            idx = byte_index - row_stride
            has_line1 = line_number > 0
            has_line2 = line_number > 1 and line2_shift >= 0
            line1 = data[idx] if has_line1 else 0
            line2 = data[idx - row_stride] << line2_shift if has_line2 else 0
            context = ((line1 >> init_shift) & init_mask1) | (
                (line2 >> init_shift) & init_mask2
            )
            up_idx = idx + 1
            up2_idx = idx - row_stride + 1
            skip_row = line_number * skip_stride
            if fast:
                a = dec.a
                c = dec.c
                ct = dec.ct
                index = cx.index

            x = 0
            while x < padded_width:
                result = 0
                next_byte = x + 8
                read_next = next_byte < width

                if has_line1:
                    line1 = ((line1 << 8) & _MASK32) | (data[up_idx] if read_next else 0)

                if has_line2:
                    line2 = ((line2 << 8) & _MASK32) | (
                        data[up2_idx] << line2_shift if read_next else 0
                    )

                minor_width = 8 if read_next else min(width - x, 8)

                if fast:
                    # ``result`` collects the bits MSB-first by shifting left
                    # and is aligned to the byte's high end after the loop.
                    for shift in (
                        context_shifts if minor_width == 8 else context_shifts[:minor_width]
                    ):
                        # Inlined ArithmeticDecoder.decode (E.3.2).
                        row = qe_table[cx_arr[context] & 0x7F]
                        qe_value = row[0]
                        a -= qe_value
                        qe_high = row[4]
                        if c < qe_high:
                            # LPS_EXCHANGE
                            mps = mps_arr[context]
                            if a < qe_value:
                                cx_arr[context] = row[1]
                                bit = mps
                            else:
                                if row[3] == 1:
                                    mps_arr[context] = mps ^ 1
                                cx_arr[context] = row[2]
                                bit = 1 - mps
                            a = qe_value
                            # RENORMD
                            n = renorm_shifts[a]
                            if ct >= n:
                                a <<= n
                                c = (c << n) & _MASK32
                                ct -= n
                            else:
                                while True:
                                    if ct == 0:
                                        dec.c = c
                                        dec._byte_in()
                                        c = dec.c
                                        ct = dec.ct
                                    a <<= 1
                                    c = (c << 1) & _MASK32
                                    ct -= 1
                                    if a & 0x8000:
                                        break
                        else:
                            c -= qe_high
                            if a & 0x8000:
                                bit = mps_arr[context]
                            else:
                                # MPS_EXCHANGE
                                mps = mps_arr[context]
                                if a < qe_value:
                                    if row[3] == 1:
                                        mps_arr[context] = mps ^ 1
                                    cx_arr[context] = row[2]
                                    bit = 1 - mps
                                else:
                                    cx_arr[context] = row[1]
                                    bit = mps
                                # RENORMD
                                n = renorm_shifts[a]
                                if ct >= n:
                                    a <<= n
                                    c = (c << n) & _MASK32
                                    ct -= n
                                else:
                                    while True:
                                        if ct == 0:
                                            dec.c = c
                                            dec._byte_in()
                                            c = dec.c
                                            ct = dec.ct
                                        a <<= 1
                                        c = (c << 1) & _MASK32
                                        ct -= 1
                                        if a & 0x8000:
                                            break

                        result = (result << 1) | bit
                        index = context
                        # The masks keep every term below bit 16, so the
                        # upstream ``& 0xFFFF`` is a no-op here.
                        context = (
                            ((context & context_mask) << 1)
                            | bit
                            | ((line1 >> shift) & line1_bit)
                            | ((line2 >> shift) & line2_bit)
                        )
                    if minor_width != 8:
                        result <<= 8 - minor_width
                else:
                    for minor_x, (to_shift, shift) in enumerate(shifts[:minor_width]):
                        if override_at is not None:
                            index = override_at(
                                context,
                                x + minor_x,
                                line_number,
                                result,
                                minor_x,
                                to_shift,
                            )
                        else:
                            index = context
                        cx.set_index(index)

                        if use_skip and (
                            skip_bytes[skip_row + ((x + minor_x) >> 3)] >> to_shift
                        ) & 1:
                            bit = 0
                        else:
                            bit = dec.decode(cx)

                        result |= bit << to_shift
                        context = (
                            ((context & context_mask) << 1)
                            | bit
                            | ((line1 >> shift) & line1_bit)
                            | ((line2 >> shift) & line2_bit)
                        ) & _MASK16

                data[byte_index] = result
                byte_index += 1
                up_idx += 1
                up2_idx += 1
                x = next_byte

            if fast:
                dec.a = a
                dec.c = c
                dec.ct = ct
                cx.index = index

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
