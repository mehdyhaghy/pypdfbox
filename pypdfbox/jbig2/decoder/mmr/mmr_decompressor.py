"""A decompressor for MMR compression.

Ported from ``org.apache.pdfbox.jbig2.decoder.mmr.MMRDecompressor`` (the 2-D
READ / ITU-T T.6 Group-4 decoder). It reads a CCITT-G4 coded byte stream from
an :class:`~pypdfbox.jbig2.io.image_input_stream.ImageInputStream` and produces
a :class:`~pypdfbox.jbig2.bitmap.Bitmap`.

Java ``int`` bit-buffer arithmetic is reproduced by masking the running code
register to 32 bits (``_INT_MASK``) so the wrapping left-shifts behave exactly
as Java's two's-complement ``int`` shifts. The caller masks the register down to
24 bits before the (two-level) code-table lookup.
"""

from __future__ import annotations

import logging

from pypdfbox.jbig2.bitmap import Bitmap
from pypdfbox.jbig2.decoder.mmr.mmr_constants import MMRConstants
from pypdfbox.jbig2.io.image_input_stream import ImageInputStream

logger = logging.getLogger(__name__)

_INT_MASK = 0xFFFFFFFF

FIRST_LEVEL_TABLE_SIZE = 8
FIRST_LEVEL_TABLE_MASK = (1 << FIRST_LEVEL_TABLE_SIZE) - 1
SECOND_LEVEL_TABLE_SIZE = 5
SECOND_LEVEL_TABLE_MASK = (1 << SECOND_LEVEL_TABLE_SIZE) - 1


class Code:
    """A single entry of an MMR code table: ``[bit_length, code_word, run_length]``."""

    __slots__ = ("bit_length", "code_word", "run_length", "sub_table")

    def __init__(self, code_data: list[int]) -> None:
        self.sub_table: list[Code | None] | None = None
        self.bit_length = code_data[0]
        self.code_word = code_data[1]
        self.run_length = code_data[2]

    def __str__(self) -> str:
        return f"{self.bit_length}/{self.code_word}/{self.run_length}"

    def __eq__(self, obj: object) -> bool:
        return (
            isinstance(obj, Code)
            and obj.bit_length == self.bit_length
            and obj.code_word == self.code_word
            and obj.run_length == self.run_length
        )

    def __hash__(self) -> int:
        return hash((self.bit_length, self.code_word, self.run_length))


def _create_little_endian_table(codes: list[list[int]]) -> list[Code | None]:
    """Build a two-level little-endian lookup table from a code list.

    For little endian, the tables are structured like this::

         v--------v length = FIRST_LEVEL_TABLE_LENGTH
                      v-----v length = SECOND_LEVEL_TABLE_LENGTH

         A code word which fits into the first level table (length=3)
         [Cccvvvvv]

         A code word which needs the second level table also (length=10)
         [Cccccccc] -> [ccvvv]

         "C" denotes the first code word bit
         "c" denotes a code word bit
         "v" denotes a variant bit
    """
    first_level_table: list[Code | None] = [None] * (FIRST_LEVEL_TABLE_MASK + 1)
    for cod in codes:
        code = Code(cod)
        if code.bit_length <= FIRST_LEVEL_TABLE_SIZE:
            variant_length = FIRST_LEVEL_TABLE_SIZE - code.bit_length
            base_word = code.code_word << variant_length

            for variant in range((1 << variant_length) - 1, -1, -1):
                index = base_word | variant
                first_level_table[index] = code
        else:
            # init second level table
            first_level_index = code.code_word >> (
                code.bit_length - FIRST_LEVEL_TABLE_SIZE
            )

            if first_level_table[first_level_index] is None:
                first_level_code = Code([0, 0, 0])
                first_level_code.sub_table = [None] * (SECOND_LEVEL_TABLE_MASK + 1)
                first_level_table[first_level_index] = first_level_code

            # fill second level table
            if code.bit_length <= FIRST_LEVEL_TABLE_SIZE + SECOND_LEVEL_TABLE_SIZE:
                holder = first_level_table[first_level_index]
                assert holder is not None and holder.sub_table is not None
                second_level_table = holder.sub_table
                variant_length = (
                    FIRST_LEVEL_TABLE_SIZE + SECOND_LEVEL_TABLE_SIZE - code.bit_length
                )
                base_word = (code.code_word << variant_length) & SECOND_LEVEL_TABLE_MASK

                for variant in range((1 << variant_length) - 1, -1, -1):
                    second_level_table[base_word | variant] = code
            else:
                raise ValueError("Code table overflow in MMRDecompressor")
    return first_level_table


class MMRDecompressor:
    """A decompressor for MMR compression."""

    _white_table: list[Code | None] | None = None
    _black_table: list[Code | None] | None = None
    _mode_table: list[Code | None] | None = None

    class RunData:
        """A class encapsulating the compressed raw data."""

        MAX_RUN_DATA_BUFFER = 1024 << 7  # 1024 * 128
        MIN_RUN_DATA_BUFFER = 3  # min. bytes to decompress
        CODE_OFFSET = 24

        def __init__(self, stream: ImageInputStream) -> None:
            self.stream = stream
            self.offset = 0
            self.last_offset = 1
            self.last_code = 0
            self.buffer_base = 0
            self.buffer_top = 0

            try:
                length = stream.length()

                length = min(max(self.MIN_RUN_DATA_BUFFER, length), self.MAX_RUN_DATA_BUFFER)

                self.buffer = bytearray(length)
                self.fill_buffer(0)
            except OSError as e:
                self.buffer = bytearray(10)
                logger.warning("%s", e)

        def uncompress_get_code(self, table: list[Code | None]) -> Code | None:
            return self.uncompress_get_code_little_endian(table)

        def uncompress_get_code_little_endian(
            self, table: list[Code | None]
        ) -> Code | None:
            code = self.uncompress_get_next_code_little_endian() & 0xFFFFFF
            result = table[code >> (self.CODE_OFFSET - FIRST_LEVEL_TABLE_SIZE)]

            # perform second-level lookup
            if result is not None and result.sub_table is not None:
                result = result.sub_table[
                    (
                        code
                        >> (
                            self.CODE_OFFSET
                            - FIRST_LEVEL_TABLE_SIZE
                            - SECOND_LEVEL_TABLE_SIZE
                        )
                    )
                    & SECOND_LEVEL_TABLE_MASK
                ]

            return result

        def uncompress_get_next_code_little_endian(self) -> int:
            """Fill up the code word in little endian mode.

            This is a hotspot, therefore the algorithm is heavily optimised. For
            the frequent cases (i.e. short words) we try to get away with as
            little work as possible.

            This method returns code words of 16 bits, which are aligned to the
            24th bit. The lowest 8 bits are used as a "queue" of bits so that an
            access to the actual data is only needed, when this queue becomes
            empty.
            """
            try:
                # the number of bits to fill (offset difference)
                bits_to_fill = self.offset - self.last_offset

                # check whether we can refill, or need to fill in absolute mode
                if bits_to_fill < 0 or bits_to_fill > 24:
                    # refill at absolute offset
                    byte_offset = (self.offset >> 3) - self.buffer_base

                    if byte_offset >= self.buffer_top:
                        byte_offset += self.buffer_base
                        self.fill_buffer(byte_offset)
                        byte_offset -= self.buffer_base

                    self.last_code = (
                        (self.buffer[byte_offset] & 0xFF) << 16
                        | (self.buffer[byte_offset + 1] & 0xFF) << 8
                        | (self.buffer[byte_offset + 2] & 0xFF)
                    )

                    bit_offset = self.offset & 7
                    self.last_code = (self.last_code << bit_offset) & _INT_MASK
                else:
                    # the offset to the next byte boundary as seen from the last offset
                    bit_offset = self.last_offset & 7
                    avail = 7 - bit_offset

                    # check whether there are enough bits in the "queue"
                    if bits_to_fill <= avail:
                        self.last_code = (self.last_code << bits_to_fill) & _INT_MASK
                    else:
                        byte_offset = (self.last_offset >> 3) + 3 - self.buffer_base

                        if byte_offset >= self.buffer_top:
                            byte_offset += self.buffer_base
                            self.fill_buffer(byte_offset)
                            byte_offset -= self.buffer_base

                        bit_offset = 8 - bit_offset
                        while True:
                            self.last_code = (self.last_code << bit_offset) & _INT_MASK
                            self.last_code |= self.buffer[byte_offset] & 0xFF
                            bits_to_fill -= bit_offset
                            byte_offset += 1
                            bit_offset = 8
                            if bits_to_fill < 8:
                                break

                        self.last_code = (
                            self.last_code << bits_to_fill
                        ) & _INT_MASK  # shift the rest
                self.last_offset = self.offset

                return self.last_code
            except IndexError as e:
                # will this actually happen? only with broken data, I'd say.
                raise IndexError(
                    "Corrupted RLE data caused by an IOException while reading raw data: "
                    + str(e)
                ) from e

        def fill_buffer(self, byte_offset: int) -> None:
            self.buffer_base = byte_offset
            try:
                self.stream.seek(byte_offset)
                self.buffer_top = self.stream.read_full(self.buffer)
            except EOFError:
                # you never know which kind of EOF will kick in
                self.buffer_top = -1
            # check filling degree
            if -1 < self.buffer_top < 3:
                # CK: if filling degree is too small,
                # smoothly fill up to the next three bytes or substitute with
                # empty bytes
                while self.buffer_top < 3:
                    try:
                        read = self.stream.read()
                    except EOFError:
                        read = -1
                    self.buffer[self.buffer_top] = 0 if read == -1 else (read & 0xFF)
                    self.buffer_top += 1
            # leave some room, in order to save a few tests in the calling code
            self.buffer_top -= 3

            if self.buffer_top < 0:
                # if we're at EOF, just supply zero-bytes
                for i in range(len(self.buffer)):
                    self.buffer[i] = 0
                self.buffer_top = len(self.buffer) - 3

        def align(self) -> None:
            """Skip to next byte."""
            self.offset = ((self.offset + 7) >> 3) << 3

    def __init__(self, width: int, height: int, stream: ImageInputStream) -> None:
        self.width = width
        self.height = height

        self.data = MMRDecompressor.RunData(stream)

        MMRDecompressor.init_tables()

    @classmethod
    def init_tables(cls) -> None:
        if cls._white_table is None:
            cls._white_table = _create_little_endian_table(MMRConstants.WhiteCodes)
            cls._black_table = _create_little_endian_table(MMRConstants.BlackCodes)
            cls._mode_table = _create_little_endian_table(MMRConstants.ModeCodes)

    def uncompress_2d(
        self,
        run_data: RunData,
        reference_offsets: list[int],
        ref_run_length: int,
        run_offsets: list[int],
        width: int,
    ) -> int:
        reference_buffer_offset = 0
        current_buffer_offset = 0
        current_line_bit_position = 0

        white_run = True  # Always start with a white run
        code: Code | None = None  # Storage var for current code being processed

        # Java arrays reject negative indices with ArrayIndexOutOfBoundsException
        # (MMRDecompressor.java:303-304), but Python lists silently wrap a
        # negative index to the tail. When a previous line returned EOL the caller
        # passes ref_run_length == MMRConstants.EOL (-1) here; reproduce Java's
        # uncaught throw rather than scribbling on the wrong slot and decoding on.
        if ref_run_length < 0:
            raise IndexError(
                f"Index {ref_run_length} out of bounds for length "
                f"{len(reference_offsets)}"
            )

        reference_offsets[ref_run_length] = reference_offsets[ref_run_length + 1] = width
        reference_offsets[ref_run_length + 2] = reference_offsets[ref_run_length + 3] = (
            width + 1
        )

        mode_table = self._mode_table
        white_table = self._white_table
        black_table = self._black_table
        assert mode_table is not None
        assert white_table is not None
        assert black_table is not None

        try:
            while current_line_bit_position < width:
                # Get the mode code
                code = run_data.uncompress_get_code(mode_table)

                if code is None:
                    run_data.offset += 1
                    break

                # Add the code length to the bit offset
                run_data.offset += code.bit_length

                run_length = code.run_length

                if run_length == MMRConstants.CODE_V0:
                    current_line_bit_position = reference_offsets[reference_buffer_offset]
                elif run_length == MMRConstants.CODE_VR1:
                    current_line_bit_position = (
                        reference_offsets[reference_buffer_offset] + 1
                    )
                elif run_length == MMRConstants.CODE_VL1:
                    current_line_bit_position = (
                        reference_offsets[reference_buffer_offset] - 1
                    )
                elif run_length == MMRConstants.CODE_H:
                    broke_out = False
                    while True:
                        code = run_data.uncompress_get_code(
                            white_table if white_run else black_table
                        )

                        if code is None:
                            broke_out = True
                            break

                        run_data.offset += code.bit_length
                        if code.run_length < 64:
                            if code.run_length < 0:
                                run_offsets[current_buffer_offset] = (
                                    current_line_bit_position
                                )
                                current_buffer_offset += 1
                                code = None
                                broke_out = True
                                break
                            current_line_bit_position += code.run_length
                            run_offsets[current_buffer_offset] = current_line_bit_position
                            current_buffer_offset += 1
                            break
                        current_line_bit_position += code.run_length
                    if broke_out:
                        break

                    first_half_bit_pos = current_line_bit_position
                    while True:
                        code = run_data.uncompress_get_code(
                            white_table if not white_run else black_table
                        )
                        if code is None:
                            broke_out = True
                            break

                        run_data.offset += code.bit_length
                        if code.run_length < 64:
                            if code.run_length < 0:
                                run_offsets[current_buffer_offset] = (
                                    current_line_bit_position
                                )
                                current_buffer_offset += 1
                                broke_out = True
                                break
                            current_line_bit_position += code.run_length
                            # don't generate 0-length run at EOL for cases where
                            # the line ends in an H-run.
                            if (
                                current_line_bit_position < width
                                or current_line_bit_position != first_half_bit_pos
                            ):
                                run_offsets[current_buffer_offset] = (
                                    current_line_bit_position
                                )
                                current_buffer_offset += 1
                            break
                        current_line_bit_position += code.run_length
                    if broke_out:
                        break

                    while (
                        current_line_bit_position < width
                        and reference_offsets[reference_buffer_offset]
                        <= current_line_bit_position
                    ):
                        reference_buffer_offset += 2
                    continue
                elif run_length == MMRConstants.CODE_P:
                    reference_buffer_offset += 1
                    current_line_bit_position = reference_offsets[reference_buffer_offset]
                    reference_buffer_offset += 1
                    continue
                elif run_length == MMRConstants.CODE_VR2:
                    current_line_bit_position = (
                        reference_offsets[reference_buffer_offset] + 2
                    )
                elif run_length == MMRConstants.CODE_VL2:
                    current_line_bit_position = (
                        reference_offsets[reference_buffer_offset] - 2
                    )
                elif run_length == MMRConstants.CODE_VR3:
                    current_line_bit_position = (
                        reference_offsets[reference_buffer_offset] + 3
                    )
                elif run_length == MMRConstants.CODE_VL3:
                    current_line_bit_position = (
                        reference_offsets[reference_buffer_offset] - 3
                    )
                else:
                    # MMRConstants.EOL and default
                    logger.warning(
                        "Should not happen! code.runLength: %s", code.run_length
                    )
                    # Possibly MMR Decoded
                    if run_data.offset == 12 and code.run_length == MMRConstants.EOL:
                        run_data.offset = 0
                        self.uncompress_1d(run_data, reference_offsets, width)
                        run_data.offset += 1
                        self.uncompress_1d(run_data, run_offsets, width)
                        ret_code = self.uncompress_1d(run_data, reference_offsets, width)
                        run_data.offset += 1
                        return ret_code
                    current_line_bit_position = width
                    continue

                # Only vertical modes get this far
                if current_line_bit_position <= width:
                    white_run = not white_run

                    run_offsets[current_buffer_offset] = current_line_bit_position
                    current_buffer_offset += 1

                    if reference_buffer_offset > 0:
                        reference_buffer_offset -= 1
                    else:
                        reference_buffer_offset += 1

                    while (
                        current_line_bit_position < width
                        and reference_offsets[reference_buffer_offset]
                        <= current_line_bit_position
                    ):
                        reference_buffer_offset += 2
        except Exception:  # noqa: BLE001 - mirrors upstream catch (Throwable)
            strbuf = (
                f"whiteRun           = {white_run}\n"
                f"code               = {code}\n"
                f"refOffset          = {reference_buffer_offset}\n"
                f"curOffset          = {current_buffer_offset}\n"
                f"bitPos             = {current_line_bit_position}\n"
                f"runData.offset = {run_data.offset} "
                f"( byte:{run_data.offset // 8}, bit:{run_data.offset & 0x07} )"
            )
            logger.warning("%s", strbuf)
            return MMRConstants.EOF

        if run_offsets[current_buffer_offset] != width:
            run_offsets[current_buffer_offset] = width

        if code is None:
            return MMRConstants.EOL
        return current_buffer_offset

    def uncompress(self) -> Bitmap:
        result = Bitmap(self.width, self.height)

        current_offsets = [0] * (self.width + 5)
        reference_offsets = [0] * (self.width + 5)
        reference_offsets[0] = self.width
        ref_run_length = 1

        for line in range(self.height):
            count = self.uncompress_2d(
                self.data, reference_offsets, ref_run_length, current_offsets, self.width
            )

            if count == MMRConstants.EOF:
                break

            if count > 0:
                self.fill_bitmap(result, line, current_offsets, count)

            # Swap lines
            reference_offsets, current_offsets = current_offsets, reference_offsets
            ref_run_length = count

        self.detect_and_skip_eol()

        self.data.align()

        return result

    def detect_and_skip_eol(self) -> None:
        assert self._mode_table is not None
        while True:
            code = self.data.uncompress_get_code(self._mode_table)
            if code is not None and code.run_length == MMRConstants.EOL:
                self.data.offset += code.bit_length
            else:
                break

    def fill_bitmap(
        self, result: Bitmap, line: int, current_offsets: list[int], count: int
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

    def uncompress_1d(
        self, run_data: RunData, run_offsets: list[int], width: int
    ) -> int:
        white_run = True
        i_bit_pos = 0
        code: Code | None = None
        ref_offset = 0

        assert self._white_table is not None
        assert self._black_table is not None

        while i_bit_pos < width:
            while True:
                if white_run:
                    code = run_data.uncompress_get_code(self._white_table)
                else:
                    code = run_data.uncompress_get_code(self._black_table)

                run_data.offset += code.bit_length

                if code.run_length < 0:
                    break

                i_bit_pos += code.run_length

                if code.run_length < 64:
                    white_run = not white_run
                    run_offsets[ref_offset] = i_bit_pos
                    ref_offset += 1
                    break
            if code.run_length < 0:
                break

        if run_offsets[ref_offset] != width:
            run_offsets[ref_offset] = width

        return (
            ref_offset
            if code is not None and code.run_length != MMRConstants.EOL
            else MMRConstants.EOL
        )
