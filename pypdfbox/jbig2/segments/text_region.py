"""Text region segment (JBIG2 §7.4.3, §6.4 decode).

Port of ``org.apache.pdfbox.jbig2.segments.TextRegion``. A text region places
instances of symbols (taken from a referred-to symbol dictionary) onto a region
bitmap. Decoding (§6.4) reads, per strip and per symbol instance, the strip
T-coordinate (STRIPT / CURT), the S-coordinate run (FIRSTS / IDS / CURS), the
symbol ID, and an optional per-instance refinement bitmap, then composites each
symbol bitmap (``IB``) onto the region bitmap with the configured combination
operator, transposition and reference corner.

Two coding modes are supported, mirroring upstream:

* **Arithmetic** — the IADT / IAFS / IADS / IAIT / IARI / IARDW / IARDH / IARDX /
  IARDY integer contexts plus the IAID symbol-code decoder.
* **Huffman** — the standard tables (§B.6 - §B.15) or user-supplied tables
  selected by the ``SBHUFF*`` flags, plus a per-region symbol-ID Huffman table
  built from the run-code lengths (§7.4.3.1.7).

Per-instance refinement is delegated to
:class:`~pypdfbox.jbig2.decoder.generic_refinement_region_decoding_procedure.GenericRefinementRegionDecodingProcedure`.

Java ``int``/``short`` masking: the symbol-instance count is read as 32 unsigned
bits; the ``SBDSOFFSET`` field is a 5-bit signed value (sign-extended by
subtracting ``0x20`` when ``> 0x0f``); the region/Huffman flag fields are masked
to mirror the upstream ``(short)`` casts.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from pypdfbox.jbig2.decoder.arithmetic.arithmetic_decoder import ArithmeticDecoder
from pypdfbox.jbig2.decoder.arithmetic.arithmetic_integer_decoder import (
    LONG_MAX_VALUE,
    ArithmeticIntegerDecoder,
)
from pypdfbox.jbig2.decoder.arithmetic.cx import CX
from pypdfbox.jbig2.decoder.generic_refinement_region_decoding_procedure import (
    GenericRefinementRegionDecodingProcedure,
)
from pypdfbox.jbig2.decoder.huffman.encoded_table import EncodedTable
from pypdfbox.jbig2.decoder.huffman.fixed_size_table import FixedSizeTable
from pypdfbox.jbig2.decoder.huffman.huffman_table import Code
from pypdfbox.jbig2.decoder.huffman.standard_tables import StandardTables
from pypdfbox.jbig2.err.invalid_header_value_exception import (
    InvalidHeaderValueException,
)
from pypdfbox.jbig2.image.bitmaps import Bitmaps
from pypdfbox.jbig2.region import Region
from pypdfbox.jbig2.segments.region_segment_information import RegionSegmentInformation
from pypdfbox.jbig2.util.combination_operator import CombinationOperator

if TYPE_CHECKING:
    from pypdfbox.jbig2.bitmap import Bitmap
    from pypdfbox.jbig2.decoder.huffman.huffman_table import HuffmanTable
    from pypdfbox.jbig2.io.sub_input_stream import SubInputStream
    from pypdfbox.jbig2.segment_header import SegmentHeader


class TextRegion(Region):
    """Segment type "Text region", 7.4.3 (page 56)."""

    def __init__(
        self,
        sub_input_stream: SubInputStream | None = None,
        segment_header: SegmentHeader | None = None,
    ) -> None:
        self.sub_input_stream = sub_input_stream

        # Region segment information field, 7.4.1
        self.region_info: RegionSegmentInformation | None = None
        if sub_input_stream is not None:
            self.region_info = RegionSegmentInformation(sub_input_stream)

        # Text region segment flags, 7.4.3.1.1
        self.sbr_template = 0
        self.sbds_offset = 0  # 6.4.8
        self.default_pixel = 0
        self.combination_operator: CombinationOperator | None = None
        self.is_transposed = 0
        self.reference_corner = 0
        self.log_sb_strips = 0
        self.use_refinement = False
        self.is_huffman_encoded = False

        # Text region segment Huffman flags, 7.4.3.1.2
        self.sb_huff_r_size = 0
        self.sb_huff_rdy = 0
        self.sb_huff_rdx = 0
        self.sb_huff_rd_height = 0
        self.sb_huff_rd_width = 0
        self.sb_huff_dt = 0
        self.sb_huff_ds = 0
        self.sb_huff_fs = 0

        # Text region refinement AT flags, 7.4.3.1.3
        self.sbr_at_x: list[int] | None = None
        self.sbr_at_y: list[int] | None = None

        # Number of symbol instances, 7.4.3.1.4
        self.amount_of_symbol_instances = 0

        # Further parameters
        self.current_s = 0
        self.sb_strips = 0
        self.amount_of_symbols = 0

        self.region_bitmap: Bitmap | None = None
        self.symbols: list[Bitmap] = []

        self.arithmetic_decoder: ArithmeticDecoder | None = None
        self.integer_decoder: ArithmeticIntegerDecoder | None = None

        self.cx_iadt: CX | None = None
        self.cx_iafs: CX | None = None
        self.cx_iads: CX | None = None
        self.cx_iait: CX | None = None
        self.cx_iari: CX | None = None
        self.cx_iardw: CX | None = None
        self.cx_iardh: CX | None = None
        self.cx_iaid: CX | None = None
        self.cx_iardx: CX | None = None
        self.cx_iardy: CX | None = None
        self.cx: CX | None = None

        # codeTable including a code to each symbol used in that region
        self.symbol_code_length = 0
        self.symbol_code_table: FixedSizeTable | None = None
        self.segment_header = segment_header

        # User-supplied tables
        self.fs_table: HuffmanTable | None = None
        self.ds_table: HuffmanTable | None = None
        self.table: HuffmanTable | None = None
        self.rdw_table: HuffmanTable | None = None
        self.rdh_table: HuffmanTable | None = None
        self.rdx_table: HuffmanTable | None = None
        self.rdy_table: HuffmanTable | None = None
        self.r_size_table: HuffmanTable | None = None

    def _parse_header(self) -> None:
        self.region_info.parse_header()

        self._read_region_flags()

        if self.is_huffman_encoded:
            self._read_huffman_flags()

        self._read_use_refinement()

        self._read_amount_of_symbol_instances()

        # 7.4.3.1.7
        self._get_symbols()

        self._compute_symbol_code_length()

        self._check_input()

    def _read_region_flags(self) -> None:
        # Bit 15
        self.sbr_template = self.sub_input_stream.read_bit()

        # Bit 10-14
        self.sbds_offset = self.sub_input_stream.read_bits(5)
        if self.sbds_offset > 0x0F:
            self.sbds_offset -= 0x20

        # Bit 9
        self.default_pixel = self.sub_input_stream.read_bit()

        # Bit 7-8
        self.combination_operator = CombinationOperator.translate_operator_code_to_enum(
            self.sub_input_stream.read_bits(2) & 0x3
        )

        # Bit 6
        self.is_transposed = self.sub_input_stream.read_bit()

        # Bit 4-5
        self.reference_corner = self.sub_input_stream.read_bits(2) & 0x3

        # Bit 2-3
        self.log_sb_strips = self.sub_input_stream.read_bits(2) & 0x3
        self.sb_strips = 1 << self.log_sb_strips

        # Bit 1
        if self.sub_input_stream.read_bit() == 1:
            self.use_refinement = True

        # Bit 0
        if self.sub_input_stream.read_bit() == 1:
            self.is_huffman_encoded = True

    def _read_huffman_flags(self) -> None:
        # Bit 15
        self.sub_input_stream.read_bit()  # Dirty read...

        # Bit 14
        self.sb_huff_r_size = self.sub_input_stream.read_bit()

        # Bit 12-13
        self.sb_huff_rdy = self.sub_input_stream.read_bits(2) & 0xF

        # Bit 10-11
        self.sb_huff_rdx = self.sub_input_stream.read_bits(2) & 0xF

        # Bit 8-9
        self.sb_huff_rd_height = self.sub_input_stream.read_bits(2) & 0xF

        # Bit 6-7
        self.sb_huff_rd_width = self.sub_input_stream.read_bits(2) & 0xF

        # Bit 4-5
        self.sb_huff_dt = self.sub_input_stream.read_bits(2) & 0xF

        # Bit 2-3
        self.sb_huff_ds = self.sub_input_stream.read_bits(2) & 0xF

        # Bit 0-1
        self.sb_huff_fs = self.sub_input_stream.read_bits(2) & 0xF

    def _read_use_refinement(self) -> None:
        if self.use_refinement and self.sbr_template == 0:
            self.sbr_at_x = [0, 0]
            self.sbr_at_y = [0, 0]

            # Byte 0
            self.sbr_at_x[0] = self.sub_input_stream.read_byte()
            # Byte 1
            self.sbr_at_y[0] = self.sub_input_stream.read_byte()
            # Byte 2
            self.sbr_at_x[1] = self.sub_input_stream.read_byte()
            # Byte 3
            self.sbr_at_y[1] = self.sub_input_stream.read_byte()

    def _read_amount_of_symbol_instances(self) -> None:
        self.amount_of_symbol_instances = (
            self.sub_input_stream.read_bits(32) & 0xFFFFFFFF
        )

        # sanity check: don't decode more than one symbol per pixel
        pixels = self.region_info.get_bitmap_width() * self.region_info.get_bitmap_height()
        if pixels < self.amount_of_symbol_instances:
            self.amount_of_symbol_instances = pixels

    def _get_symbols(self) -> None:
        if self.segment_header.get_rt_segments() is not None:
            self._init_symbols()

    def _compute_symbol_code_length(self) -> None:
        if self.is_huffman_encoded:
            self._symbol_id_code_lengths()
        else:
            self.symbol_code_length = int(
                math.ceil(math.log(self.amount_of_symbols) / math.log(2))
            )

    def _check_input(self) -> None:
        if not self.use_refinement and self.sbr_template != 0:
            self.sbr_template = 0

        if (
            self.sb_huff_fs == 2
            or self.sb_huff_rd_width == 2
            or self.sb_huff_rd_height == 2
            or self.sb_huff_rdx == 2
            or self.sb_huff_rdy == 2
        ):
            raise InvalidHeaderValueException(
                "Huffman flag value of text region segment is not permitted"
            )

        if not self.use_refinement:
            if self.sb_huff_r_size != 0:
                self.sb_huff_r_size = 0
            if self.sb_huff_rdy != 0:
                self.sb_huff_rdy = 0
            if self.sb_huff_rdx != 0:
                self.sb_huff_rdx = 0
            if self.sb_huff_rd_width != 0:
                self.sb_huff_rd_width = 0
            if self.sb_huff_rd_height != 0:
                self.sb_huff_rd_height = 0

    def get_region_bitmap(self) -> Bitmap:
        if not self.is_huffman_encoded:
            self._set_coding_statistics()

        self._create_region_bitmap()
        self._decode_symbol_instances()

        # 4)
        return self.region_bitmap

    def _set_coding_statistics(self) -> None:
        if self.cx_iadt is None:
            self.cx_iadt = CX(512, 1)

        if self.cx_iafs is None:
            self.cx_iafs = CX(512, 1)

        if self.cx_iads is None:
            self.cx_iads = CX(512, 1)

        if self.cx_iait is None:
            self.cx_iait = CX(512, 1)

        if self.cx_iari is None:
            self.cx_iari = CX(512, 1)

        if self.cx_iardw is None:
            self.cx_iardw = CX(512, 1)

        if self.cx_iardh is None:
            self.cx_iardh = CX(512, 1)

        if self.cx_iaid is None:
            self.cx_iaid = CX(1 << self.symbol_code_length, 1)

        if self.cx_iardx is None:
            self.cx_iardx = CX(512, 1)

        if self.cx_iardy is None:
            self.cx_iardy = CX(512, 1)

        if self.arithmetic_decoder is None:
            self.arithmetic_decoder = ArithmeticDecoder(self.sub_input_stream)

        if self.integer_decoder is None:
            self.integer_decoder = ArithmeticIntegerDecoder(self.arithmetic_decoder)

    def _create_region_bitmap(self) -> None:
        # 6.4.5
        width = self.region_info.get_bitmap_width()
        height = self.region_info.get_bitmap_height()
        from pypdfbox.jbig2.bitmap import Bitmap

        self.region_bitmap = Bitmap(width, height)

        # 1)
        if self.default_pixel != 0:
            self.region_bitmap.fill_bitmap(0xFF)

    def _decode_strip_t(self) -> int:
        strip_t = 0
        # 2)
        if self.is_huffman_encoded:
            # 6.4.6
            if self.sb_huff_dt == 3:
                if self.table is None:
                    dt_nr = 0

                    if self.sb_huff_fs == 3:
                        dt_nr += 1

                    if self.sb_huff_ds == 3:
                        dt_nr += 1

                    self.table = self._get_user_table(dt_nr)
                strip_t = self.table.decode(self.sub_input_stream)
            else:
                strip_t = StandardTables.get_table(11 + self.sb_huff_dt).decode(
                    self.sub_input_stream
                )
        else:
            strip_t = self.integer_decoder.decode(self.cx_iadt)

        return strip_t * -self.sb_strips

    def _decode_symbol_instances(self) -> None:
        strip_t = self._decode_strip_t()

        # Last two sentences of 6.4.5 2)
        first_s = 0
        instance_counter = 0

        # 6.4.5 3 a)
        while instance_counter < self.amount_of_symbol_instances:
            d_t = self._decode_dt()
            strip_t += d_t

            # 3 c) symbol instances in the strip
            first = True
            self.current_s = 0

            # do until OOB
            while True:
                # 3 c) i) - first symbol instance in the strip
                if first:
                    # 6.4.7
                    dfs = self._decode_dfs()
                    first_s += dfs
                    self.current_s = first_s
                    first = False
                    # 3 c) ii) - the remaining symbol instances in the strip
                else:
                    # 6.4.8
                    id_s = self._decode_id_s()

                    # If result is OOB, then all the symbol instances in this
                    # strip have been decoded; proceed to step 3 d) respectively
                    # 3 b). Also exit, if the expected number of instances have
                    # been decoded.
                    #
                    # The latter exit condition guards against pathological
                    # cases where a strip's S never contains OOB and thus never
                    # terminates as illustrated in
                    # https://bugs.chromium.org/p/chromium/issues/detail?id=450971
                    # case pdfium-loop2.pdf.
                    if (
                        id_s == LONG_MAX_VALUE
                        or instance_counter >= self.amount_of_symbol_instances
                    ):
                        break

                    self.current_s += id_s + self.sbds_offset

                # 3 c) iii)
                current_t = self._decode_current_t()
                t = strip_t + current_t

                # 3 c) iv)
                id_ = self._decode_id()

                # 3 c) v)
                r = self._decode_ri()
                # 6.4.11
                ib = self._decode_ib(r, id_)

                # vi)
                self._blit(ib, t)

                instance_counter += 1

    def _decode_dt(self) -> int:
        # 3) b)
        # 6.4.6
        if self.is_huffman_encoded:
            if self.sb_huff_dt == 3:
                d_t = self.table.decode(self.sub_input_stream)
            else:
                d_t = StandardTables.get_table(11 + self.sb_huff_dt).decode(
                    self.sub_input_stream
                )
        else:
            d_t = self.integer_decoder.decode(self.cx_iadt)

        return d_t * self.sb_strips

    def _decode_dfs(self) -> int:
        if self.is_huffman_encoded:
            if self.sb_huff_fs == 3:
                if self.fs_table is None:
                    self.fs_table = self._get_user_table(0)
                return self.fs_table.decode(self.sub_input_stream)
            else:
                return StandardTables.get_table(6 + self.sb_huff_fs).decode(
                    self.sub_input_stream
                )
        else:
            return self.integer_decoder.decode(self.cx_iafs)

    def _decode_id_s(self) -> int:
        if self.is_huffman_encoded:
            if self.sb_huff_ds == 3:
                if self.ds_table is None:
                    ds_nr = 0
                    if self.sb_huff_fs == 3:
                        ds_nr += 1

                    self.ds_table = self._get_user_table(ds_nr)
                return self.ds_table.decode(self.sub_input_stream)
            else:
                return StandardTables.get_table(8 + self.sb_huff_ds).decode(
                    self.sub_input_stream
                )
        else:
            return self.integer_decoder.decode(self.cx_iads)

    def _decode_current_t(self) -> int:
        if self.sb_strips != 1:
            if self.is_huffman_encoded:
                return self.sub_input_stream.read_bits(self.log_sb_strips)
            else:
                return self.integer_decoder.decode(self.cx_iait)

        return 0

    def _decode_id(self) -> int:
        if self.is_huffman_encoded:
            if self.symbol_code_table is None:
                return self.sub_input_stream.read_bits(self.symbol_code_length)

            return self.symbol_code_table.decode(self.sub_input_stream)
        else:
            return self.integer_decoder.decode_iaid(
                self.cx_iaid, self.symbol_code_length
            )

    def _decode_ri(self) -> int:
        if self.use_refinement:
            if self.is_huffman_encoded:
                return self.sub_input_stream.read_bit()
            else:
                return self.integer_decoder.decode(self.cx_iari)
        return 0

    def _decode_ib(self, r: int, id_: int) -> Bitmap:
        if r == 0:
            ib = self.symbols[id_]
        else:
            # 1) - 4)
            rdw = self._decode_rdw()
            rdh = self._decode_rdh()
            rdx = self._decode_rdx()
            rdy = self._decode_rdy()

            # 5)
            sym_in_ref_size = 0
            if self.is_huffman_encoded:
                sym_in_ref_size = self._decode_sym_in_ref_size()
                self.sub_input_stream.skip_bits()
            stream_position0 = self.sub_input_stream.get_stream_position()

            # 6)
            ibo = self.symbols[id_]
            wo = ibo.get_width()
            ho = ibo.get_height()

            generic_region_reference_dx = (rdw >> 1) + rdx
            generic_region_reference_dy = (rdh >> 1) + rdy

            if self.arithmetic_decoder is None:
                self.arithmetic_decoder = ArithmeticDecoder(self.sub_input_stream)

            if self.cx is None:
                self.cx = CX(65536, 1)

            ib = GenericRefinementRegionDecodingProcedure.decode(
                self.arithmetic_decoder,
                self.cx,
                wo + rdw,
                ho + rdh,
                self.sbr_template,
                False,
                ibo,
                generic_region_reference_dx,
                generic_region_reference_dy,
                self.sbr_at_x,
                self.sbr_at_y,
            )

            # 7
            if self.is_huffman_encoded:
                # Make sure that the processed bytes are not more than
                # sym_in_ref_size
                if (
                    self.sub_input_stream.get_stream_position()
                    > stream_position0 + sym_in_ref_size
                ):
                    raise OSError(
                        f"Refinement bitmap bytes expected: {sym_in_ref_size}, "
                        f"bytes read: "
                        f"{self.sub_input_stream.get_stream_position() - stream_position0}"
                    )
                # needed if less
                self.sub_input_stream.seek(stream_position0 + sym_in_ref_size)
        return ib

    def _decode_rdw(self) -> int:
        if self.is_huffman_encoded:
            if self.sb_huff_rd_width == 3:
                if self.rdw_table is None:
                    rdw_nr = 0
                    if self.sb_huff_fs == 3:
                        rdw_nr += 1

                    if self.sb_huff_ds == 3:
                        rdw_nr += 1

                    if self.sb_huff_dt == 3:
                        rdw_nr += 1

                    self.rdw_table = self._get_user_table(rdw_nr)
                return self.rdw_table.decode(self.sub_input_stream)
            else:
                return StandardTables.get_table(14 + self.sb_huff_rd_width).decode(
                    self.sub_input_stream
                )
        else:
            return self.integer_decoder.decode(self.cx_iardw)

    def _decode_rdh(self) -> int:
        if self.is_huffman_encoded:
            if self.sb_huff_rd_height == 3:
                if self.rdh_table is None:
                    rdh_nr = 0

                    if self.sb_huff_fs == 3:
                        rdh_nr += 1

                    if self.sb_huff_ds == 3:
                        rdh_nr += 1

                    if self.sb_huff_dt == 3:
                        rdh_nr += 1

                    if self.sb_huff_rd_width == 3:
                        rdh_nr += 1

                    self.rdh_table = self._get_user_table(rdh_nr)
                return self.rdh_table.decode(self.sub_input_stream)
            else:
                return StandardTables.get_table(14 + self.sb_huff_rd_height).decode(
                    self.sub_input_stream
                )
        else:
            return self.integer_decoder.decode(self.cx_iardh)

    def _decode_rdx(self) -> int:
        if self.is_huffman_encoded:
            if self.sb_huff_rdx == 3:
                if self.rdx_table is None:
                    rdx_nr = 0
                    if self.sb_huff_fs == 3:
                        rdx_nr += 1

                    if self.sb_huff_ds == 3:
                        rdx_nr += 1

                    if self.sb_huff_dt == 3:
                        rdx_nr += 1

                    if self.sb_huff_rd_width == 3:
                        rdx_nr += 1

                    if self.sb_huff_rd_height == 3:
                        rdx_nr += 1

                    self.rdx_table = self._get_user_table(rdx_nr)
                return self.rdx_table.decode(self.sub_input_stream)
            else:
                return StandardTables.get_table(14 + self.sb_huff_rdx).decode(
                    self.sub_input_stream
                )
        else:
            return self.integer_decoder.decode(self.cx_iardx)

    def _decode_rdy(self) -> int:
        if self.is_huffman_encoded:
            if self.sb_huff_rdy == 3:
                if self.rdy_table is None:
                    rdy_nr = 0
                    if self.sb_huff_fs == 3:
                        rdy_nr += 1

                    if self.sb_huff_ds == 3:
                        rdy_nr += 1

                    if self.sb_huff_dt == 3:
                        rdy_nr += 1

                    if self.sb_huff_rd_width == 3:
                        rdy_nr += 1

                    if self.sb_huff_rd_height == 3:
                        rdy_nr += 1

                    if self.sb_huff_rdx == 3:
                        rdy_nr += 1

                    self.rdy_table = self._get_user_table(rdy_nr)
                return self.rdy_table.decode(self.sub_input_stream)
            else:
                return StandardTables.get_table(14 + self.sb_huff_rdy).decode(
                    self.sub_input_stream
                )
        else:
            return self.integer_decoder.decode(self.cx_iardy)

    def _decode_sym_in_ref_size(self) -> int:
        if self.sb_huff_r_size == 0:
            return StandardTables.get_table(1).decode(self.sub_input_stream)
        else:
            if self.r_size_table is None:
                r_size_nr = 0

                if self.sb_huff_fs == 3:
                    r_size_nr += 1

                if self.sb_huff_ds == 3:
                    r_size_nr += 1

                if self.sb_huff_dt == 3:
                    r_size_nr += 1

                if self.sb_huff_rd_width == 3:
                    r_size_nr += 1

                if self.sb_huff_rd_height == 3:
                    r_size_nr += 1

                if self.sb_huff_rdx == 3:
                    r_size_nr += 1

                if self.sb_huff_rdy == 3:
                    r_size_nr += 1

                self.r_size_table = self._get_user_table(r_size_nr)
            return self.r_size_table.decode(self.sub_input_stream)

    def _blit(self, ib: Bitmap, t: int) -> None:
        if self.is_transposed == 0 and self.reference_corner in (2, 3):
            self.current_s += ib.get_width() - 1
        elif self.is_transposed == 1 and self.reference_corner in (0, 2):
            self.current_s += ib.get_height() - 1

        # vii)
        s = self.current_s

        # viii)
        if self.is_transposed == 1:
            t, s = s, t

        if self.reference_corner != 1:
            if self.reference_corner == 0:
                # BL
                t -= ib.get_height() - 1
            elif self.reference_corner == 2:
                # BR
                t -= ib.get_height() - 1
                s -= ib.get_width() - 1
            elif self.reference_corner == 3:
                # TR
                s -= ib.get_width() - 1

        Bitmaps.blit(ib, self.region_bitmap, s, t, self.combination_operator)

        # x)
        if self.is_transposed == 0 and self.reference_corner in (0, 1):
            self.current_s += ib.get_width() - 1

        if self.is_transposed == 1 and self.reference_corner in (1, 3):
            self.current_s += ib.get_height() - 1

    def _init_symbols(self) -> None:
        for segment in self.segment_header.get_rt_segments():
            if segment.get_segment_type() == 0:
                sd = segment.get_segment_data()

                sd.cx_iaid = self.cx_iaid
                self.symbols.extend(sd.get_dictionary())
        self.amount_of_symbols = len(self.symbols)

    def _get_user_table(self, table_position: int) -> HuffmanTable | None:
        table_counter = 0

        for referred_to_segment_header in self.segment_header.get_rt_segments():
            if referred_to_segment_header.get_segment_type() == 53:
                if table_counter == table_position:
                    t = referred_to_segment_header.get_segment_data()
                    return EncodedTable(t)
                else:
                    table_counter += 1
        return None

    def _symbol_id_code_lengths(self) -> None:
        # 1) - 2)
        run_code_table: list[Code] = []

        for i in range(35):
            pref_len = self.sub_input_stream.read_bits(4) & 0xF
            if pref_len > 0:
                run_code_table.append(Code(pref_len, 0, i, False))

        ht: HuffmanTable = FixedSizeTable(run_code_table)

        # 3) - 5)
        previous_code_length = 0

        counter = 0
        sb_sym_codes: list[Code] = []
        while counter < self.amount_of_symbols:
            code = ht.decode(self.sub_input_stream)
            if code < 32:
                if code > 0:
                    sb_sym_codes.append(Code(code, 0, counter, False))

                previous_code_length = code
                counter += 1
            else:
                run_length = 0
                curr_code_length = 0
                if code == 32:
                    run_length = 3 + self.sub_input_stream.read_bits(2)
                    if counter > 0:
                        curr_code_length = previous_code_length
                elif code == 33:
                    run_length = 3 + self.sub_input_stream.read_bits(3)
                elif code == 34:
                    run_length = 11 + self.sub_input_stream.read_bits(7)

                for _j in range(run_length):
                    if curr_code_length > 0:
                        sb_sym_codes.append(Code(curr_code_length, 0, counter, False))
                    counter += 1

        # 6) - Skip over remaining bits in the last Byte read
        self.sub_input_stream.skip_bits()

        # 7)
        self.symbol_code_table = FixedSizeTable(sb_sym_codes)

    def init(self, header: SegmentHeader, sis: SubInputStream) -> None:
        self.segment_header = header
        self.sub_input_stream = sis
        self.region_info = RegionSegmentInformation(self.sub_input_stream)
        self._parse_header()

    def set_contexts(
        self,
        cx: CX | None,
        cx_iadt: CX | None,
        cx_iafs: CX | None,
        cx_iads: CX | None,
        cx_iait: CX | None,
        cx_iaid: CX | None,
        cx_iardw: CX | None,
        cx_iardh: CX | None,
        cx_iardx: CX | None,
        cx_iardy: CX | None,
    ) -> None:
        self.cx = cx

        self.cx_iadt = cx_iadt
        self.cx_iafs = cx_iafs
        self.cx_iads = cx_iads
        self.cx_iait = cx_iait

        self.cx_iaid = cx_iaid

        self.cx_iardw = cx_iardw
        self.cx_iardh = cx_iardh
        self.cx_iardx = cx_iardx
        self.cx_iardy = cx_iardy

    def set_parameters(
        self,
        arithmetic_decoder: ArithmeticDecoder | None,
        i_decoder: ArithmeticIntegerDecoder | None,
        is_huffman_encoded: bool,
        sb_refine: bool,
        sbw: int,
        sbh: int,
        sb_num_instances: int,
        sb_strips: int,
        sb_num_syms: int,
        sb_default_pixel: int,
        sb_combination_operator: int,
        transposed: int,
        ref_corner: int,
        sbds_offset: int,
        sb_huff_fs: int,
        sb_huff_ds: int,
        sb_huff_dt: int,
        sb_huff_rd_width: int,
        sb_huff_rd_height: int,
        sb_huff_rdx: int,
        sb_huff_rdy: int,
        sb_huff_r_size: int,
        sbr_template: int,
        sbr_at_x: list[int] | None,
        sbr_at_y: list[int] | None,
        sb_syms: list[Bitmap],
        sb_sym_code_len: int,
    ) -> None:
        self.arithmetic_decoder = arithmetic_decoder

        self.integer_decoder = i_decoder

        self.is_huffman_encoded = is_huffman_encoded
        self.use_refinement = sb_refine

        self.region_info.set_bitmap_width(sbw)
        self.region_info.set_bitmap_height(sbh)

        self.amount_of_symbol_instances = sb_num_instances
        self.sb_strips = sb_strips
        self.amount_of_symbols = sb_num_syms
        self.default_pixel = sb_default_pixel
        self.combination_operator = (
            CombinationOperator.translate_operator_code_to_enum(sb_combination_operator)
        )
        self.is_transposed = transposed
        self.reference_corner = ref_corner
        self.sbds_offset = sbds_offset

        self.sb_huff_fs = sb_huff_fs
        self.sb_huff_ds = sb_huff_ds
        self.sb_huff_dt = sb_huff_dt
        self.sb_huff_rd_width = sb_huff_rd_width
        self.sb_huff_rd_height = sb_huff_rd_height
        self.sb_huff_rdx = sb_huff_rdx
        self.sb_huff_rdy = sb_huff_rdy
        self.sb_huff_r_size = sb_huff_r_size

        self.sbr_template = sbr_template
        self.sbr_at_x = sbr_at_x
        self.sbr_at_y = sbr_at_y

        self.symbols = sb_syms
        self.symbol_code_length = sb_sym_code_len

    def get_region_info(self) -> RegionSegmentInformation:
        return self.region_info
