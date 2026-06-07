"""Symbol dictionary segment (JBIG2 §7.4.2 parsing, §6.5 decode).

Port of ``org.apache.pdfbox.jbig2.segments.SymbolDictionary``. Decodes a
dictionary of symbol bitmaps using either arithmetic coding (the height-class /
delta-width loop with ``GenericRegion``-style direct symbol decoding, and the
optional refinement/aggregation path via ``GenericRefinementRegion`` +
``TextRegion``) or Huffman coding (height-class collective bitmaps + run-length
export flags). Parsing is described in 7.4.2.1.1 - 7.4.1.1.5; the decoding
procedure is described in 6.5.

The text-region aggregate path (§6.5.8.2 step 2, more than one aggregation
instance) delegates to ``TextRegion`` (one-strip text region, Table 17). The
direct arithmetic path, the single-instance refinement path, the aggregate path
and the full Huffman path all work.

Java ``int`` masking: the exported-symbol counts (``amountOfExportSymbolss`` /
``amountOfNewSymbols``) are read as 32 unsigned bits and stored as Python ints;
upstream stores them in a signed ``int`` (so a value with bit 31 set becomes
negative and is caught by the explicit ``< 0`` validation in
:meth:`_get_to_export_flags`). To mirror that overflow-detection behaviour the
32-bit reads are sign-extended into the signed-``int`` range.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from pypdfbox.jbig2.bitmap import Bitmap
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
from pypdfbox.jbig2.decoder.huffman.standard_tables import StandardTables
from pypdfbox.jbig2.dictionary import Dictionary
from pypdfbox.jbig2.err.invalid_header_value_exception import (
    InvalidHeaderValueException,
)
from pypdfbox.jbig2.image.bitmaps import Bitmaps
from pypdfbox.jbig2.segments.generic_region import GenericRegion

if TYPE_CHECKING:
    from pypdfbox.jbig2.decoder.huffman.huffman_table import HuffmanTable
    from pypdfbox.jbig2.io.sub_input_stream import SubInputStream
    from pypdfbox.jbig2.region import Region
    from pypdfbox.jbig2.segment_header import SegmentHeader

# Java Integer.MAX_VALUE — used by the imported+new symbol-count validation.
_INTEGER_MAX_VALUE = 0x7FFFFFFF


def _to_signed_int32(value: int) -> int:
    """Sign-extend a 32-bit value into the Java signed ``int`` range."""
    value &= 0xFFFFFFFF
    return value - 0x100000000 if value >= 0x80000000 else value


class SymbolDictionary(Dictionary):
    """A symbol dictionary segment.

    Parsing is described in 7.4.2.1.1 - 7.4.1.1.5. The decoding procedure is
    described in 6.5.
    """

    def __init__(
        self,
        sub_input_stream: SubInputStream | None = None,
        segment_header: SegmentHeader | None = None,
    ) -> None:
        self.sub_input_stream = sub_input_stream
        self.segment_header = segment_header

        # Symbol dictionary flags, 7.4.2.1.1
        self.sdr_template = 0
        self.sd_template = 0
        self.is_coding_context_retained = False
        self.is_coding_context_used = False
        self.sd_huff_agg_instance_selection = 0
        self.sd_huff_bm_size_selection = 0
        self.sd_huff_decode_width_selection = 0
        self.sd_huff_decode_height_selection = 0
        self.use_refinement_aggregation = False
        self.is_huffman_encoded = False

        # Symbol dictionary AT flags, 7.4.2.1.2
        self.sd_at_x: list[int] | None = None
        self.sd_at_y: list[int] | None = None

        # Symbol dictionary refinement AT flags, 7.4.2.1.3
        self.sdr_at_x: list[int] | None = None
        self.sdr_at_y: list[int] | None = None

        # Number of exported symbols, 7.4.2.1.4
        self.amount_of_export_symbolss = 0

        # Number of new symbols, 7.4.2.1.5
        self.amount_of_new_symbols = 0

        # Further parameters
        self.amount_of_imported_symbols = 0
        self.import_symbols: list[Bitmap] | None = None
        self.amount_of_decoded_symbols = 0
        self.new_symbols: list[Bitmap | None] | None = None

        # User-supplied tables
        self.dh_table: HuffmanTable | None = None
        self.dw_table: HuffmanTable | None = None
        self.bm_size_table: HuffmanTable | None = None
        self.agg_inst_table: HuffmanTable | None = None

        # Return value of that segment
        self.export_symbols: list[Bitmap] | None = None
        self.sb_symbols: list[Bitmap] | None = None

        self.arithmetic_decoder: ArithmeticDecoder | None = None
        self.i_decoder: ArithmeticIntegerDecoder | None = None

        self.text_region = None
        self.generic_region: GenericRegion | None = None
        self.cx: CX | None = None

        self.cx_iadh: CX | None = None
        self.cx_iadw: CX | None = None
        self.cx_iaai: CX | None = None
        self.cx_iaex: CX | None = None
        self.cx_iardx: CX | None = None
        self.cx_iardy: CX | None = None
        self.cx_iadt: CX | None = None

        self.cx_iaid: CX | None = None
        self.sb_sym_code_len = 0

        self.last_symbol_dictionary: SymbolDictionary | None = None

    def _parse_header(self) -> None:
        self._read_region_flags()
        self._set_at_pixels()
        self._set_refinement_at_pixels()
        self._read_amount_of_exported_symbols()
        self._read_amount_of_new_symbols()
        self._set_in_syms()

        is_context_adopted = False

        rt_segments = self.segment_header.get_rt_segments()

        if rt_segments is not None:
            for i in range(len(rt_segments) - 1, -1, -1):
                if rt_segments[i].get_segment_type() == 0:
                    self.last_symbol_dictionary = rt_segments[i].get_segment_data()

                    if (
                        self.is_coding_context_used
                        and self.last_symbol_dictionary.is_coding_context_retained
                    ):
                        self._validate_context_values(self.last_symbol_dictionary)
                        is_context_adopted = True
                    break

        if self.is_coding_context_used and not is_context_adopted:
            raise InvalidHeaderValueException(
                "Coding context reuse requested, but no referred symbol "
                "dictionary found"
                if self.last_symbol_dictionary is None
                else "Coding context reuse requested, but last referred symbol "
                "dictionary does not retain coding context"
            )

        self._check_input()

    def _read_region_flags(self) -> None:
        # Bit 13-15
        self.sub_input_stream.read_bits(3)  # Dirty read... reserved bits must be 0

        # Bit 12
        self.sdr_template = self.sub_input_stream.read_bit()

        # Bit 10-11
        self.sd_template = self.sub_input_stream.read_bits(2) & 0xF

        # Bit 9
        if self.sub_input_stream.read_bit() == 1:
            self.is_coding_context_retained = True

        # Bit 8
        if self.sub_input_stream.read_bit() == 1:
            self.is_coding_context_used = True

        # Bit 7
        self.sd_huff_agg_instance_selection = self.sub_input_stream.read_bit()

        # Bit 6
        self.sd_huff_bm_size_selection = self.sub_input_stream.read_bit()

        # Bit 4-5
        self.sd_huff_decode_width_selection = self.sub_input_stream.read_bits(2) & 0xF

        # Bit 2-3
        self.sd_huff_decode_height_selection = self.sub_input_stream.read_bits(2) & 0xF

        # Bit 1
        if self.sub_input_stream.read_bit() == 1:
            self.use_refinement_aggregation = True

        # Bit 0
        if self.sub_input_stream.read_bit() == 1:
            self.is_huffman_encoded = True

    def _set_at_pixels(self) -> None:
        if not self.is_huffman_encoded:
            if self.sd_template == 0:
                self._read_at_pixels(4)
            else:
                self._read_at_pixels(1)

    def _set_refinement_at_pixels(self) -> None:
        if self.use_refinement_aggregation and self.sdr_template == 0:
            self._read_refinement_at_pixels(2)

    def _read_at_pixels(self, amount_of_pixels: int) -> None:
        self.sd_at_x = [0] * amount_of_pixels
        self.sd_at_y = [0] * amount_of_pixels

        for i in range(amount_of_pixels):
            self.sd_at_x[i] = self.sub_input_stream.read_byte()
            self.sd_at_y[i] = self.sub_input_stream.read_byte()

    def _read_refinement_at_pixels(self, amount_of_at_pixels: int) -> None:
        self.sdr_at_x = [0] * amount_of_at_pixels
        self.sdr_at_y = [0] * amount_of_at_pixels

        for i in range(amount_of_at_pixels):
            self.sdr_at_x[i] = self.sub_input_stream.read_byte()
            self.sdr_at_y[i] = self.sub_input_stream.read_byte()

    def _read_amount_of_exported_symbols(self) -> None:
        self.amount_of_export_symbolss = _to_signed_int32(
            self.sub_input_stream.read_bits(32)
        )

    def _read_amount_of_new_symbols(self) -> None:
        self.amount_of_new_symbols = _to_signed_int32(
            self.sub_input_stream.read_bits(32)
        )

    def _set_in_syms(self) -> None:
        if self.segment_header.get_rt_segments() is not None:
            self._retrieve_import_symbols()
        else:
            self.import_symbols = []

    def _adopt_retained_coding_contexts(self, sd: SymbolDictionary) -> None:
        """Adopt retained arithmetic coding context from another dictionary.

        Per spec §7.4.2.2, only bitmap coding statistics (CX) are reused;
        configuration compatibility is validated in :meth:`_parse_header` before
        this is called, and ``ArithmeticDecoder`` must not be reused as it is
        bound to the current stream.
        """
        self.cx = sd.cx.copy()

    def _validate_context_values(self, sd: SymbolDictionary) -> None:
        """Validate the dictionary whose context values are being reused.

        The values of SDHUFF, SDREFAGG, SDTEMPLATE, SDRTEMPLATE, and all of the
        AT locations (both direct and refinement) must match the corresponding
        values from the symbol dictionary whose context values are being used.
        """
        if (
            self.is_huffman_encoded != sd.is_huffman_encoded
            or self.use_refinement_aggregation != sd.use_refinement_aggregation
            or self.sd_template != sd.sd_template
            or self.sdr_template != sd.sdr_template
            or self.sd_at_x != sd.sd_at_x
            or self.sd_at_y != sd.sd_at_y
            or self.sdr_at_x != sd.sdr_at_x
            or self.sdr_at_y != sd.sdr_at_y
        ):
            raise InvalidHeaderValueException(
                "SymbolDictionary reuse values don't match"
            )

    def _check_input(self) -> None:
        if self.is_huffman_encoded:
            if self.sd_template != 0:
                self.sd_template = 0
            if not self.use_refinement_aggregation:
                if self.is_coding_context_retained:
                    self.is_coding_context_retained = False

                if self.is_coding_context_used:
                    self.is_coding_context_used = False
        else:
            if self.sd_huff_bm_size_selection != 0:
                self.sd_huff_bm_size_selection = 0
            if self.sd_huff_decode_width_selection != 0:
                self.sd_huff_decode_width_selection = 0
            if self.sd_huff_decode_height_selection != 0:
                self.sd_huff_decode_height_selection = 0

        if not self.use_refinement_aggregation and self.sdr_template != 0:
            self.sdr_template = 0

        if (not self.is_huffman_encoded or not self.use_refinement_aggregation) and (
            self.sd_huff_agg_instance_selection != 0
        ):
            self.sd_huff_agg_instance_selection = 0

    def get_dictionary(self) -> list[Bitmap]:
        """6.5.5 Decoding the symbol dictionary.

        :return: List of decoded symbol bitmaps.
        """
        if self.export_symbols is None:
            if self.use_refinement_aggregation:
                self.sb_sym_code_len = self._get_sb_sym_code_len()

            # decodes all referred segments including last_symbol_dictionary
            self._set_symbols_array()

            # Bitmap CX needed for both arithmetic path and huffman+refinement path
            if not self.is_huffman_encoded or self.use_refinement_aggregation:
                if self.is_coding_context_used:
                    self._adopt_retained_coding_contexts(self.last_symbol_dictionary)
                else:
                    self._reset_bitmap_coding_statistics()

            # Integer coders only needed for arithmetic path
            if not self.is_huffman_encoded:
                self._reset_integer_coder_statistics()

            # 6.5.5 1)
            self.new_symbols = [None] * self.amount_of_new_symbols

            # 6.5.5 2)
            new_symbols_widths: list[int] | None = None
            if self.is_huffman_encoded and not self.use_refinement_aggregation:
                new_symbols_widths = [0] * self.amount_of_new_symbols

            # 6.5.5 3)
            height_class_height = 0
            self.amount_of_decoded_symbols = 0

            # 6.5.5 4 a)
            while self.amount_of_decoded_symbols < self.amount_of_new_symbols:
                # 6.5.5 4 b)
                height_class_height += self._decode_height_class_delta_height()
                symbol_width = 0
                total_width = 0
                height_class_first_symbol_index = self.amount_of_decoded_symbols

                # 6.5.5 4 c)

                # Repeat until OOB - OOB sends a break.
                while True:
                    # 4 c) i)
                    difference_width = self._decode_difference_width()

                    # If result is OOB, then all the symbols in this height class
                    # have been decoded; proceed to step 4 d). Also exit if the
                    # expected number of symbols have been decoded.
                    #
                    # The latter exit condition guards against pathological cases
                    # where a symbol's DW never contains OOB and thus never
                    # terminates.
                    if (
                        difference_width == LONG_MAX_VALUE
                        or self.amount_of_decoded_symbols >= self.amount_of_new_symbols
                    ):
                        break

                    symbol_width += difference_width
                    total_width += symbol_width

                    # 4 c) ii)
                    if not self.is_huffman_encoded or self.use_refinement_aggregation:
                        if not self.use_refinement_aggregation:
                            # 6.5.8.1 - Direct coded
                            self._decode_directly_through_generic_region(
                                symbol_width, height_class_height
                            )
                        else:
                            # 6.5.8.2 - Refinement/Aggregate-coded
                            self._decode_aggregate(symbol_width, height_class_height)
                    elif self.is_huffman_encoded and not self.use_refinement_aggregation:
                        # 4 c) iii)
                        new_symbols_widths[self.amount_of_decoded_symbols] = (
                            symbol_width
                        )
                    self.amount_of_decoded_symbols += 1

                # 6.5.5 4 d)
                if self.is_huffman_encoded and not self.use_refinement_aggregation:
                    # 6.5.9
                    if self.sd_huff_bm_size_selection == 0:
                        bm_size = StandardTables.get_table(1).decode(
                            self.sub_input_stream
                        )
                    else:
                        bm_size = self._huff_decode_bm_size()

                    self.sub_input_stream.skip_bits()

                    height_class_collective_bitmap = (
                        self._decode_height_class_collective_bitmap(
                            bm_size, height_class_height, total_width
                        )
                    )

                    self.sub_input_stream.skip_bits()
                    self._decode_height_class_bitmap(
                        height_class_collective_bitmap,
                        height_class_first_symbol_index,
                        height_class_height,
                        new_symbols_widths,
                    )

            # 5)
            # 6.5.10 1) - 5)
            ex_flags = self._get_to_export_flags()

            # 6.5.10 6) - 8)
            self._set_exported_symbols(ex_flags)

        return self.export_symbols

    def _reset_bitmap_coding_statistics(self) -> None:
        """Step 4 (§7.4.2.2): reset bitmap arithmetic coding statistics to zero.

        Only the bitmap CX is reset here; integer coder contexts are separate
        (step 5).
        """
        self.cx = CX(65536, 1)

    def _reset_integer_coder_statistics(self) -> None:
        """Step 5 (§7.4.2.2): reset all integer-coder arithmetic contexts."""
        self.cx_iadt = CX(512, 1)
        self.cx_iadh = CX(512, 1)
        self.cx_iadw = CX(512, 1)
        self.cx_iaai = CX(512, 1)
        self.cx_iaex = CX(512, 1)

        if self.use_refinement_aggregation:
            self.cx_iaid = CX(1 << self.sb_sym_code_len, 1)
            self.cx_iardx = CX(512, 1)
            self.cx_iardy = CX(512, 1)

        self.arithmetic_decoder = ArithmeticDecoder(self.sub_input_stream)
        self.i_decoder = ArithmeticIntegerDecoder(self.arithmetic_decoder)

    def _decode_height_class_bitmap(
        self,
        height_class_collective_bitmap: Bitmap,
        height_class_first_symbol: int,
        height_class_height: int,
        new_symbols_widths: list[int],
    ) -> None:
        for i in range(height_class_first_symbol, self.amount_of_decoded_symbols):
            start_column = 0

            for j in range(height_class_first_symbol, i):
                start_column += new_symbols_widths[j]

            roi = (start_column, 0, new_symbols_widths[i], height_class_height)
            symbol_bitmap = Bitmaps.extract(roi, height_class_collective_bitmap)
            self.new_symbols[i] = symbol_bitmap
            self.sb_symbols.append(symbol_bitmap)

    def _decode_aggregate(self, symbol_width: int, height_class_height: int) -> None:
        # 6.5.8.2 1)
        # 6.5.8.2.1 - Number of symbol instances in aggregation
        if self.is_huffman_encoded:
            amount_of_refinement_aggregation_instances = (
                self._huff_decode_ref_agg_n_inst()
            )
        else:
            amount_of_refinement_aggregation_instances = self.i_decoder.decode(
                self.cx_iaai
            )

        if amount_of_refinement_aggregation_instances > 1:
            # 6.5.8.2 2)
            self._decode_through_text_region(
                symbol_width,
                height_class_height,
                amount_of_refinement_aggregation_instances,
            )
        elif amount_of_refinement_aggregation_instances == 1:
            # 6.5.8.2 3) refers to 6.5.8.2.2
            self._decode_refined_symbol(symbol_width, height_class_height)

    def _huff_decode_ref_agg_n_inst(self) -> int:
        if self.sd_huff_agg_instance_selection == 0:
            return StandardTables.get_table(1).decode(self.sub_input_stream)
        elif self.sd_huff_agg_instance_selection == 1:
            if self.agg_inst_table is None:
                aggregation_instance_number = 0

                if self.sd_huff_decode_height_selection == 3:
                    aggregation_instance_number += 1
                if self.sd_huff_decode_width_selection == 3:
                    aggregation_instance_number += 1
                if self.sd_huff_bm_size_selection == 3:
                    aggregation_instance_number += 1

                self.agg_inst_table = self._get_user_table(aggregation_instance_number)
            return self.agg_inst_table.decode(self.sub_input_stream)
        return 0

    def _decode_through_text_region(
        self,
        symbol_width: int,
        height_class_height: int,
        amount_of_refinement_aggregation_instances: int,
    ) -> None:
        # 6.5.8.2 2) - decode the aggregate symbol via a one-strip TextRegion.
        from pypdfbox.jbig2.segments.text_region import TextRegion

        if self.text_region is None:
            self.text_region = TextRegion(self.sub_input_stream, None)

            self.text_region.set_contexts(
                self.cx,  # default context
                CX(512, 1),  # IADT
                CX(512, 1),  # IAFS
                CX(512, 1),  # IADS
                CX(512, 1),  # IAIT
                self.cx_iaid,  # IAID
                CX(512, 1),  # IARDW
                CX(512, 1),  # IARDH
                CX(512, 1),  # IARDX
                CX(512, 1),  # IARDY
            )

        # 6.5.8.2.4 Concatenating the array used as parameter later.
        self._set_symbols_array()

        # 6.5.8.2 2) Parameters set according to Table 17, page 36
        self.text_region.set_parameters(
            self.arithmetic_decoder,
            self.i_decoder,
            self.is_huffman_encoded,
            True,
            symbol_width,
            height_class_height,
            amount_of_refinement_aggregation_instances,
            1,
            self.amount_of_imported_symbols + self.amount_of_decoded_symbols,
            0,
            0,
            0,
            1,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            self.sdr_template,
            self.sdr_at_x,
            self.sdr_at_y,
            self.sb_symbols,
            self.sb_sym_code_len,
        )

        self._add_symbol(self.text_region)

    def _decode_refined_symbol(
        self, symbol_width: int, height_class_height: int
    ) -> None:
        sym_in_ref_size = 0
        stream_position0 = 0
        if self.is_huffman_encoded:
            # 2) - 4)
            id_ = self.sub_input_stream.read_bits(self.sb_sym_code_len)
            rdx = StandardTables.get_table(15).decode(self.sub_input_stream)
            rdy = StandardTables.get_table(15).decode(self.sub_input_stream)

            # 5) a)
            sym_in_ref_size = StandardTables.get_table(1).decode(self.sub_input_stream)

            # 5) b) - Skip over remaining bits
            self.sub_input_stream.skip_bits()

            stream_position0 = self.sub_input_stream.get_stream_position()

            # 5) c) - Initialize arithmetic decoder for refinement bitmap.
            # Note that the same sub_input_stream is used for both symbol
            # dictionary decoding and refinement bitmap decoding.
            self.arithmetic_decoder = ArithmeticDecoder(self.sub_input_stream)
        else:
            # 2) - 4)
            id_ = self.i_decoder.decode_iaid(self.cx_iaid, self.sb_sym_code_len)
            rdx = self.i_decoder.decode(self.cx_iardx)
            rdy = self.i_decoder.decode(self.cx_iardy)

        # 6)
        self._set_symbols_array()
        ibo = self.sb_symbols[id_]
        self._decode_new_symbols(symbol_width, height_class_height, ibo, rdx, rdy)

        # 7)
        if self.is_huffman_encoded:
            # Make sure that the processed bytes are not more than sym_in_ref_size
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

    def _decode_new_symbols(
        self, sym_width: int, hc_height: int, ibo: Bitmap, rdx: int, rdy: int
    ) -> None:
        """Decode a new symbol via the generic refinement region procedure."""
        # cx (bitmap coding context) must already be initialized via
        # get_dictionary(). It is required by
        # GenericRefinementRegionDecodingProcedure.decode and provides the
        # arithmetic decoder statistics for bitmap decoding.
        if self.cx is None:
            raise RuntimeError("CX not initialized (bug in initialization order)")

        # arithmetic_decoder must already be initialized for the current
        # bitstream context. Defensive guard — unreachable on every decode path
        # (get_dictionary always constructs the decoder before a refined symbol
        # is decoded); mirrors upstream SymbolDictionary.decodeNewSymbols line
        # 746 (an IllegalStateException that is likewise structurally dead).
        if self.arithmetic_decoder is None:  # pragma: no cover
            raise RuntimeError("ArithmeticDecoder not initialized")

        # Parameters as shown in Table 18, page 36
        symbol = GenericRefinementRegionDecodingProcedure.decode(
            self.arithmetic_decoder,
            self.cx,
            sym_width,
            hc_height,
            self.sdr_template,
            False,
            ibo,
            rdx,
            rdy,
            self.sdr_at_x,
            self.sdr_at_y,
        )

        self.new_symbols[self.amount_of_decoded_symbols] = symbol
        self.sb_symbols.append(symbol)

    def _decode_directly_through_generic_region(
        self, sym_width: int, hc_height: int
    ) -> None:
        if self.generic_region is None:
            self.generic_region = GenericRegion(self.sub_input_stream)

        # Parameters set according to Table 16, page 35
        self.generic_region.set_parameters(
            False,
            sd_template=self.sd_template,
            is_tpgdon=False,
            use_skip=False,
            gb_at_x=self.sd_at_x,
            gb_at_y=self.sd_at_y,
            sym_width=sym_width,
            hc_height=hc_height,
            cx=self.cx,
            arithmetic_decoder=self.arithmetic_decoder,
        )

        self._add_symbol(self.generic_region)

    def _add_symbol(self, region: Region) -> None:
        symbol = region.get_region_bitmap()
        self.new_symbols[self.amount_of_decoded_symbols] = symbol
        self.sb_symbols.append(symbol)

    def _decode_difference_width(self) -> int:
        if self.is_huffman_encoded:
            if self.sd_huff_decode_width_selection == 0:
                return StandardTables.get_table(2).decode(self.sub_input_stream)
            elif self.sd_huff_decode_width_selection == 1:
                return StandardTables.get_table(3).decode(self.sub_input_stream)
            elif self.sd_huff_decode_width_selection == 3:
                if self.dw_table is None:
                    dw_nr = 0

                    if self.sd_huff_decode_height_selection == 3:
                        dw_nr += 1
                    self.dw_table = self._get_user_table(dw_nr)

                return self.dw_table.decode(self.sub_input_stream)
        else:
            return self.i_decoder.decode(self.cx_iadw)
        # Unreachable: SDHUFFDW is only ever 0/1/3 (2 is reserved); mirrors the
        # `default: return 0` after the switch in upstream
        # SymbolDictionary.decodeDifferenceWidth (line 812), structurally dead.
        return 0  # pragma: no cover

    def _decode_height_class_delta_height(self) -> int:
        if self.is_huffman_encoded:
            return self._decode_height_class_delta_height_with_huffman()
        else:
            return self.i_decoder.decode(self.cx_iadh)

    def _decode_height_class_delta_height_with_huffman(self) -> int:
        """6.5.6 if is_huffman_encoded.

        :return: Result of decoding HCDH.
        """
        if self.sd_huff_decode_height_selection == 0:
            return StandardTables.get_table(4).decode(self.sub_input_stream)
        elif self.sd_huff_decode_height_selection == 1:
            return StandardTables.get_table(5).decode(self.sub_input_stream)
        elif self.sd_huff_decode_height_selection == 3:
            if self.dh_table is None:
                self.dh_table = self._get_user_table(0)
            return self.dh_table.decode(self.sub_input_stream)

        # Unreachable: SDHUFFDH is only ever 0/1/3 (2 is reserved); mirrors the
        # `default: return 0` after the switch in upstream
        # SymbolDictionary.decodeHeightClassDeltaHeightWithHuffman (line 851),
        # structurally dead.
        return 0  # pragma: no cover

    def _decode_height_class_collective_bitmap(
        self, bm_size: int, height_class_height: int, total_width: int
    ) -> Bitmap:
        if bm_size == 0:
            height_class_collective_bitmap = Bitmap(total_width, height_class_height)

            for i in range(height_class_collective_bitmap.get_length()):
                height_class_collective_bitmap.set_byte(
                    i, self.sub_input_stream.read_byte()
                )

            return height_class_collective_bitmap
        else:
            if self.generic_region is None:
                self.generic_region = GenericRegion(self.sub_input_stream)

            self.generic_region.set_parameters(
                True,
                data_offset=self.sub_input_stream.get_stream_position(),
                data_length=bm_size,
                gbh=height_class_height,
                gbw=total_width,
                variant="dict_simple",
            )

            return self.generic_region.get_region_bitmap()

    def _set_exported_symbols(self, to_export_flags: list[int]) -> None:
        self.export_symbols = []

        for i in range(self.amount_of_imported_symbols + self.amount_of_new_symbols):
            if to_export_flags[i] == 1:
                if i < self.amount_of_imported_symbols:
                    self.export_symbols.append(self.import_symbols[i])
                else:
                    self.export_symbols.append(
                        self.new_symbols[i - self.amount_of_imported_symbols]
                    )

    def _get_to_export_flags(self) -> list[int]:
        # The validation could be placed a little earlier but it is needed here
        # before the array creation.
        if (
            self.amount_of_imported_symbols < 0
            or self.amount_of_new_symbols < 0
            or self.amount_of_imported_symbols + self.amount_of_new_symbols
            > _INTEGER_MAX_VALUE
        ):
            raise InvalidHeaderValueException(
                f" Invalid number of symbols: "
                f"imported={self.amount_of_imported_symbols}, "
                f"new={self.amount_of_new_symbols}"
            )

        ex_index = 0
        cur_ex_flag = 0
        total = self.amount_of_imported_symbols + self.amount_of_new_symbols
        export_flags = [0] * total

        while ex_index < total:
            if self.is_huffman_encoded:
                ex_run_length = StandardTables.get_table(1).decode(
                    self.sub_input_stream
                )
            else:
                ex_run_length = self.i_decoder.decode(self.cx_iaex)

            if ex_run_length < 0 or ex_run_length > total - ex_index:
                raise InvalidHeaderValueException(
                    f"Invalid EXRUNLENGTH: {ex_run_length}"
                )

            for i in range(ex_index, ex_index + ex_run_length):
                export_flags[i] = cur_ex_flag

            ex_index += ex_run_length
            cur_ex_flag = 1 if cur_ex_flag == 0 else 0

        return export_flags

    def _huff_decode_bm_size(self) -> int:
        if self.bm_size_table is None:
            bm_nr = 0

            if self.sd_huff_decode_height_selection == 3:
                bm_nr += 1

            if self.sd_huff_decode_width_selection == 3:
                bm_nr += 1

            self.bm_size_table = self._get_user_table(bm_nr)
        return self.bm_size_table.decode(self.sub_input_stream)

    def _get_sb_sym_code_len(self) -> int:
        """6.5.8.2.3 - Setting SBSYMCODES and SBSYMCODELEN.

        :return: Result of computing SBSYMCODELEN.
        """
        sb_sym_code_len = math.ceil(
            math.log(self.amount_of_imported_symbols + self.amount_of_new_symbols)
            / math.log(2)
        )

        if self.is_huffman_encoded:
            return max(sb_sym_code_len, 1)
        else:
            return sb_sym_code_len

    def _set_symbols_array(self) -> None:
        """6.5.8.2.4 - Setting SBSYMS."""
        # _set_in_syms (run during _parse_header) always assigns import_symbols
        # (to the retrieved list or []), so this guard is structurally dead on
        # every decode path — mirrors upstream SymbolDictionary.setSymbolsArray
        # lines 994-997 where the same `if importSymbols == null` is unreachable.
        if self.import_symbols is None:  # pragma: no cover
            self._retrieve_import_symbols()

        if self.sb_symbols is None:
            self.sb_symbols = []
            self.sb_symbols.extend(self.import_symbols)

    def _retrieve_import_symbols(self) -> None:
        """Concatenate symbols from all referred-to segments."""
        self.import_symbols = []
        for referred_to_segment_header in self.segment_header.get_rt_segments():
            if referred_to_segment_header.get_segment_type() == 0:
                sd = referred_to_segment_header.get_segment_data()
                self.import_symbols.extend(sd.get_dictionary())
                self.amount_of_imported_symbols += sd.amount_of_export_symbolss

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

    def init(self, header: SegmentHeader, sis: SubInputStream) -> None:
        self.sub_input_stream = sis
        self.segment_header = header
        self._parse_header()
