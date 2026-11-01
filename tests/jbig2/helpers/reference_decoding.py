"""Reference (pre-optimization) JBIG2 decoding procedures for parity tests.

These are verbatim copies of the straightforward, call-per-decision
implementations that the production modules used before their hot loops were
inlined: the MQ decoder with separate LPS_EXCHANGE / MPS_EXCHANGE /
RENORMD steps, the IAx / IAID integer procedures, the generic-region
template line loops, the refinement template-0 / template-1 loops, the
unshifted blit, the MMR line fill and the halftone gray-scale plane steps. The
tests in tests/jbig2/test_inlined_decoding_parity.py decode the same inputs
with these and with the production code and require identical bitmaps and
identical decoder / context state.
"""

from pypdfbox.jbig2.bitmap import Bitmap
from pypdfbox.jbig2.decoder.arithmetic.arithmetic_decoder import QE
from pypdfbox.jbig2.decoder.arithmetic.cx import CX
from pypdfbox.jbig2.decoder.generic_refinement_region_decoding_procedure import (
    GenericRefinementRegionDecodingProcedure,
    Template,
    _java_mod,
)
from pypdfbox.jbig2.decoder.mmr.mmr_decompressor import MMRDecompressor
from pypdfbox.jbig2.image.bitmaps import Bitmaps, _to_signed_byte
from pypdfbox.jbig2.io.sub_input_stream import SubInputStream
from pypdfbox.jbig2.segments.generic_region import GenericRegion
from pypdfbox.jbig2.util.combination_operator import CombinationOperator

_MASK16 = 0xFFFF
_MASK32 = 0xFFFFFFFF


class RefArithmeticDecoder:
    """Reference MQ decoder (separate DECODE / exchange / RENORMD steps)."""

    def __init__(self, iis) -> None:
        """Bind to an ``ImageInputStream``-like reader and run ``INITDEC``.

        ``iis`` must expose the ``javax.imageio.stream.ImageInputStream``
        surface used here: ``get_stream_position()`` -> int byte offset,
        ``read()`` -> unsigned byte 0-255 or -1 at EOF (advancing the position
        by one), and ``seek(pos)`` to reposition.
        """
        self.a = 0
        self.c = 0
        self.ct = 0
        self.b = 0
        self.stream_pos0 = 0
        self.iis = iis
        self._init()

    def _init(self) -> None:
        self.stream_pos0 = self.iis.get_stream_position()
        self.b = self.iis.read()

        self.c = (self.b << 16) & _MASK32

        self._byte_in()

        self.c = (self.c << 7) & _MASK32
        self.ct -= 7
        self.a = 0x8000

    def decode(self, cx) -> int:
        icx = cx.cx()
        qe_value = QE[icx][0]

        self.a -= qe_value

        if (self.c >> 16) < qe_value:
            d = self._lps_exchange(cx, icx, qe_value)
            self._renormalize()
        else:
            self.c = (self.c - (qe_value << 16)) & _MASK32
            if (self.a & 0x8000) == 0:
                d = self._mps_exchange(cx, icx)
                self._renormalize()
            else:
                return cx.mps()

        return d

    def _byte_in(self) -> None:
        if self.iis.get_stream_position() > self.stream_pos0:
            self.iis.seek(self.iis.get_stream_position() - 1)

        self.b = self.iis.read()

        if self.b == 0xFF:
            b1 = self.iis.read()
            if b1 > 0x8F:
                self.c += 0xFF00
                self.ct = 8
                self.iis.seek(self.iis.get_stream_position() - 2)
            else:
                self.c += b1 << 9
                self.ct = 7
        else:
            self.b = self.iis.read()
            self.c += self.b << 8
            self.ct = 8

        self.c &= _MASK32

    def _renormalize(self) -> None:
        while True:
            if self.ct == 0:
                self._byte_in()

            self.a = (self.a << 1) & _MASK32
            self.c = (self.c << 1) & _MASK32
            self.ct -= 1

            if (self.a & 0x8000) != 0:
                break

        self.c &= _MASK32

    def _mps_exchange(self, cx, icx: int) -> int:
        mps = cx.mps()

        if self.a < QE[icx][0]:
            if QE[icx][3] == 1:
                cx.toggle_mps()

            cx.set_cx(QE[icx][2])
            return 1 - mps
        else:
            cx.set_cx(QE[icx][1])
            return mps

    def _lps_exchange(self, cx, icx: int, qe_value: int) -> int:
        mps = cx.mps()

        if self.a < qe_value:
            cx.set_cx(QE[icx][1])
            self.a = qe_value
            return mps
        else:
            if QE[icx][3] == 1:
                cx.toggle_mps()

            cx.set_cx(QE[icx][2])
            self.a = qe_value
            return 1 - mps



class RefArithmeticIntegerDecoder:
    """The IAx / IAID integer arithmetic decoder (Annex A)."""

    def __init__(self, decoder) -> None:
        self.decoder = decoder

    def decode(self, cx_iax: CX | None) -> int:
        """Arithmetic Integer Decoding Procedure, Annex A.2.

        ``cx_iax`` holds the contexts/statistics for the value to be decoded.
        Returns the decoded value (``Long.MAX_VALUE`` denotes OOB).
        """
        # A.2.
        # CX is identified by the rightmost 9 bits of PREV. Thus PREV always
        # contains the values of the eight most-recently-decoded bits, plus a
        # leading 1 bit, which indicates the number of bits decoded so far.
        prev = 1

        v = 0

        if cx_iax is None:
            cx_iax = CX(512, 1)

        cx_iax.set_index(prev & 0x1FF)
        s = self.decoder.decode(cx_iax)
        prev = self._set_prev(prev, s)

        cx_iax.set_index(prev & 0x1FF)
        d = self.decoder.decode(cx_iax)
        prev = self._set_prev(prev, d)

        if d == 1:
            cx_iax.set_index(prev & 0x1FF)
            d = self.decoder.decode(cx_iax)
            prev = self._set_prev(prev, d)

            if d == 1:
                cx_iax.set_index(prev & 0x1FF)
                d = self.decoder.decode(cx_iax)
                prev = self._set_prev(prev, d)

                if d == 1:
                    cx_iax.set_index(prev & 0x1FF)
                    d = self.decoder.decode(cx_iax)
                    prev = self._set_prev(prev, d)

                    if d == 1:
                        cx_iax.set_index(prev & 0x1FF)
                        d = self.decoder.decode(cx_iax)
                        prev = self._set_prev(prev, d)

                        if d == 1:
                            bits_to_read = 32
                            offset = 4436
                        else:
                            bits_to_read = 12
                            offset = 340
                    else:
                        bits_to_read = 8
                        offset = 84
                else:
                    bits_to_read = 6
                    offset = 20
            else:
                bits_to_read = 4
                offset = 4
        else:
            bits_to_read = 2
            offset = 0

        for _i in range(bits_to_read):
            cx_iax.set_index(prev & 0x1FF)
            d = self.decoder.decode(cx_iax)
            prev = self._set_prev(prev, d)
            v = (v << 1) | d

        v += offset

        if s == 0:
            return v
        elif s == 1 and v > 0:
            return -v

        return 0x7FFFFFFFFFFFFFFF

    def _set_prev(self, prev: int, bit: int) -> int:
        # Branch structure kept verbatim from upstream for behavioural parity.
        if prev < 256:  # noqa: SIM108
            prev = ((prev << 1) | bit) & 0x1FF
        else:
            prev = ((((prev << 1) | bit) & 511) | 256) & 0x1FF
        return prev

    def decode_iaid(self, cx_iaid: CX, sym_code_len: int) -> int:
        """The IAID decoding procedure, Annex A.3.

        ``cx_iaid`` holds the contexts and statistics; ``sym_code_len`` is the
        symbol code length. Returns the decoded value.
        """
        # A.3 1)
        prev = 1

        # A.3 2)
        # The spec says: "the rightmost SBSYMCODELEN + 1 bits of PREV are used"
        # but also "the number of contexts required is 2^SBSYMCODELEN". The
        # resolution: the leading 1 bit is not used for context
        # identification — only the lower N bits are.
        mask = (1 << sym_code_len) - 1

        for _i in range(sym_code_len):
            cx_iaid.set_index(prev & mask)
            prev = (prev << 1) | self.decoder.decode(cx_iaid)

        # A.3 3) & 4)
        return prev - (1 << sym_code_len)


class RefGenericRegion(GenericRegion):
    """Generic region with the original per-template line loops."""

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
                    self.arith_decoder = RefArithmeticDecoder(self.sub_input_stream)
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
            minor_width = min(width - x, 8)

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
            minor_width = min(width - x, 8)

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
            minor_width = min(width - x, 8)

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
            minor_width = min(width - x, 8)

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
            minor_width = min(width - x, 8)

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


class RefRefinementProcedure(GenericRefinementRegionDecodingProcedure):
    """Refinement procedure with the original per-pixel loops."""

    def _decode_line_explicit_t1(self, y: int, width: int) -> None:
        for x in range(width):
            self.cx.set_index(self._build_context_t1(x, y))
            self.region_bitmap.set_pixel(x, y, self.arith_decoder.decode(self.cx))

    # Template 1 — typical prediction decode (LTP=1 path, §6.3.5.6 step 3d)
    # TPGRPIX=1 when the 3x3 reference neighbourhood is uniform (§6.3.5.6 3d-i)

    def _decode_line_tpgr_t1(self, y: int, width: int) -> None:
        for x in range(width):
            center = self._get_reference_bit(x, y)
            uniform = True
            for dy in range(-1, 2):
                for dx in range(-1, 2):
                    if self._get_reference_bit(x + dx, y + dy) != center:
                        uniform = False
                        break
                if not uniform:
                    break

            if uniform:
                bit = center
            else:
                self.cx.set_index(self._build_context_t1(x, y))
                bit = self.arith_decoder.decode(self.cx)
            self.region_bitmap.set_pixel(x, y, bit)

    def _decode_template(
        self,
        line_number: int,
        width: int,
        row_stride: int,
        ref_row_stride: int,
        padded_width: int,
        delta_ref_stride: int,
        line_offset: int,
        byte_index: int,
        current_line: int,
        ref_byte_index: int,
        template_formation: Template,
    ) -> None:
        ref = self.reference_bitmap
        reg = self.region_bitmap

        w1 = w2 = w3 = w4 = 0

        if current_line >= 1 and (current_line - 1) < ref.get_height():
            w1 = ref.get_byte_as_integer(ref_byte_index - ref_row_stride)
        if current_line >= 0 and current_line < ref.get_height():
            w2 = ref.get_byte_as_integer(ref_byte_index)
        if current_line >= -1 and current_line + 1 < ref.get_height():
            w3 = ref.get_byte_as_integer(ref_byte_index + ref_row_stride)
        ref_byte_index += 1

        if line_number >= 1:
            w4 = reg.get_byte_as_integer(byte_index - row_stride)
        byte_index += 1

        mod_reference_dx = _java_mod(self.reference_dx, 8)
        shift_offset = 6 + mod_reference_dx
        mod_ref_byte_idx = ref_byte_index % ref_row_stride

        if shift_offset >= 0:
            c1 = ((0 if shift_offset >= 8 else w1 >> shift_offset) & 0x07) & 0xFFFF
            c2 = ((0 if shift_offset >= 8 else w2 >> shift_offset) & 0x07) & 0xFFFF
            c3 = ((0 if shift_offset >= 8 else w3 >> shift_offset) & 0x07) & 0xFFFF
            if shift_offset == 6 and mod_ref_byte_idx > 1:
                if current_line >= 1 and (current_line - 1) < ref.get_height():
                    c1 |= (
                        ref.get_byte_as_integer(ref_byte_index - ref_row_stride - 2)
                        << 2
                    ) & 0x04
                if current_line >= 0 and current_line < ref.get_height():
                    c2 |= (ref.get_byte_as_integer(ref_byte_index - 2) << 2) & 0x04
                if current_line >= -1 and current_line + 1 < ref.get_height():
                    c3 |= (
                        ref.get_byte_as_integer(ref_byte_index + ref_row_stride - 2)
                        << 2
                    ) & 0x04
            if shift_offset == 0:
                w1 = w2 = w3 = 0
                if mod_ref_byte_idx < ref_row_stride - 1:
                    if current_line >= 1 and (current_line - 1) < ref.get_height():
                        w1 = ref.get_byte_as_integer(ref_byte_index - ref_row_stride)
                    if current_line >= 0 and current_line < ref.get_height():
                        w2 = ref.get_byte_as_integer(ref_byte_index)
                    if current_line >= -1 and current_line + 1 < ref.get_height():
                        w3 = ref.get_byte_as_integer(ref_byte_index + ref_row_stride)
                ref_byte_index += 1
        else:
            c1 = ((w1 << 1) & 0x07) & 0xFFFF
            c2 = ((w2 << 1) & 0x07) & 0xFFFF
            c3 = ((w3 << 1) & 0x07) & 0xFFFF
            w1 = w2 = w3 = 0
            if mod_ref_byte_idx < ref_row_stride - 1:
                if current_line >= 1 and (current_line - 1) < ref.get_height():
                    w1 = ref.get_byte_as_integer(ref_byte_index - ref_row_stride)
                if current_line >= 0 and current_line < ref.get_height():
                    w2 = ref.get_byte_as_integer(ref_byte_index)
                if current_line >= -1 and current_line + 1 < ref.get_height():
                    w3 = ref.get_byte_as_integer(ref_byte_index + ref_row_stride)
                ref_byte_index += 1
            c1 = (c1 | ((w1 >> 7) & 0x07)) & 0xFFFF
            c2 = (c2 | ((w2 >> 7) & 0x07)) & 0xFFFF
            c3 = (c3 | ((w3 >> 7) & 0x07)) & 0xFFFF

        c4 = (w4 >> 6) & 0xFFFF
        c5 = 0

        # Java's ``int <<`` masks the shift count to its low 5 bits, so a
        # negative ``modBitsToTrim`` (which Java's truncated remainder can yield
        # when ``modReferenceDX`` exceeds 2) shifts by ``count & 0x1F`` rather
        # than raising; mirror that here.
        mod_bits_to_trim = _java_mod(2 - mod_reference_dx, 8) & 0x1F
        w1 = (w1 << mod_bits_to_trim) & _MASK32
        w2 = (w2 << mod_bits_to_trim) & _MASK32
        w3 = (w3 << mod_bits_to_trim) & _MASK32

        w4 = (w4 << 2) & _MASK32

        for x in range(width):
            minor_x = x & 0x07

            tval = template_formation.form(c1, c2, c3, c4, c5)

            if self.override:
                self.cx.set_index(
                    self._override_at_template0(
                        tval,
                        x,
                        line_number,
                        reg.get_byte(reg.get_byte_index(x, line_number)),
                        minor_x,
                    )
                )
            else:
                self.cx.set_index(tval)
            bit = self.arith_decoder.decode(self.cx)
            reg.set_pixel(x, line_number, bit)

            c1 = (((c1 << 1) | (0x01 & (w1 >> 7))) & 0x07) & 0xFFFF
            c2 = (((c2 << 1) | (0x01 & (w2 >> 7))) & 0x07) & 0xFFFF
            c3 = (((c3 << 1) | (0x01 & (w3 >> 7))) & 0x07) & 0xFFFF
            c4 = (((c4 << 1) | (0x01 & (w4 >> 7))) & 0x07) & 0xFFFF
            c5 = bit & 0xFFFF

            if _java_mod(x - self.reference_dx, 8) == 5:
                if ((x - self.reference_dx) // 8) + 1 >= ref.get_row_stride():
                    w1 = w2 = w3 = 0
                else:
                    if current_line >= 1 and (current_line - 1 < ref.get_height()):
                        w1 = ref.get_byte_as_integer(ref_byte_index - ref_row_stride)
                    else:
                        w1 = 0
                    if current_line >= 0 and current_line < ref.get_height():
                        w2 = ref.get_byte_as_integer(ref_byte_index)
                    else:
                        w2 = 0
                    if current_line >= -1 and (current_line + 1) < ref.get_height():
                        w3 = ref.get_byte_as_integer(ref_byte_index + ref_row_stride)
                    else:
                        w3 = 0
                ref_byte_index += 1
            else:
                w1 = (w1 << 1) & _MASK32
                w2 = (w2 << 1) & _MASK32
                w3 = (w3 << 1) & _MASK32

            if minor_x == 5 and line_number >= 1:
                if (x >> 3) + 1 >= reg.get_row_stride():
                    w4 = 0
                else:
                    w4 = reg.get_byte_as_integer(byte_index - row_stride)
                byte_index += 1
            else:
                w4 = (w4 << 1) & _MASK32


def ref_refinement_decode(
    arith_decoder,
    cx: CX,
    width: int,
    height: int,
    gr_template: int,
    is_tpgr_on: bool,
    reference_bitmap: Bitmap,
    reference_dx: int,
    reference_dy: int,
    gr_at_x: list[int] | None,
    gr_at_y: list[int] | None,
) -> Bitmap:
    """GenericRefinementRegionDecodingProcedure.decode on the reference loops."""
    return RefRefinementProcedure(arith_decoder, cx)._run(
        width,
        height,
        gr_template,
        is_tpgr_on,
        reference_bitmap,
        reference_dx,
        reference_dy,
        gr_at_x,
        gr_at_y,
    )


def ref_blit_unshifted(
    src: Bitmap,
    dst: Bitmap,
    start_line: int,
    last_line: int,
    dst_start_idx: int,
    src_start_idx: int,
    src_end_idx: int,
    op: CombinationOperator,
) -> None:
    length = src_end_idx - src_start_idx + 1  # src_end_idx is inclusive
    src_start_offset = src_start_idx
    dst_start_offset = dst_start_idx
    lines = last_line - start_line
    while lines > 0:
        src_idx = src_start_offset
        dst_idx = dst_start_offset
        count = length
        # Go through the bytes in a line of the symbol.
        if op in (
            CombinationOperator.OR,
            CombinationOperator.AND,
            CombinationOperator.XOR,
            CombinationOperator.XNOR,
        ):
            while count > 0:
                count -= 1
                dst.set_byte(
                    dst_idx,
                    Bitmaps.combine_bytes(
                        _to_signed_byte(src.get_byte(src_idx)),
                        _to_signed_byte(dst.get_byte(dst_idx)),
                        op,
                    ),
                )
                src_idx += 1
                dst_idx += 1
        elif op == CombinationOperator.REPLACE:
            Bitmap.arraycopy(src, src_idx, dst, dst_idx, count)
        src_start_offset += src.get_row_stride()
        dst_start_offset += dst.get_row_stride()
        lines -= 1


def ref_fill_bitmap(
result: Bitmap, line: int, current_offsets: list[int], count: int
) -> None:
    x = 0
    target_byte = result.get_byte_index(0, line)
    target_byte_value = 0
    for index in range(count):
        offset = current_offsets[index]

        value = 0 if (index & 1) == 0 else 1

        while x < offset:
            target_byte_value = ((target_byte_value << 1) | value) & 0xFF
            x += 1

            if (x & 7) == 0:
                result.set_byte(target_byte, target_byte_value)
                target_byte += 1
                target_byte_value = 0

    # Flush remaining bits in the last partial byte
    if (x & 7) != 0:
        target_byte_value = (target_byte_value << (8 - (x & 7))) & 0xFF
        result.set_byte(target_byte, target_byte_value)


def ref_combine_gray_scale_planes(
    gray_scale_planes: list[Bitmap], j: int
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


def ref_compute_gray_scale_values(
    h_grid_width: int,
    h_grid_height: int,
    gray_scale_planes: list[Bitmap],
    bits_per_value: int,
) -> list[list[int]]:
    # Gray-scale decoding procedure, page 98
    gray_scale_values = [
        [0] * h_grid_width for _ in range(h_grid_height)
    ]

    # 4)
    for y in range(h_grid_height):
        x = 0
        while x < h_grid_width:
            minor_width = min(h_grid_width - x, 8)
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
