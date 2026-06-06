"""Minimal JBIG2 stream encoder for parity-test fixture construction.

This is a *test helper*, not a port of any upstream class — JBIG2 has no
encoder in Apache PDFBox (the library only decodes). It exists solely to
construct complete, valid multi-segment ``.jb2`` streams that exercise the
Huffman + refinement/aggregation symbol-dictionary and Huffman text-region
decode paths, which no bundled or upstream ``.jb2`` test fixture covers.

Construction strategy
---------------------
The bit layout for every field is taken directly from ITU-T T.88 and verified
against the upstream Java decoder (``SymbolDictionary`` / ``TextRegion`` /
``SegmentHeader`` / ``JBIG2Document``). Huffman code emission reuses the port's
own :class:`StandardTable` code-assignment (canonical Annex B.3 prefix codes)
so an emitted ``(value)`` is guaranteed to round-trip through
``HuffmanTable.decode``: we look up the matching code line for the value, write
its assigned prefix bits, then the range bits (``value - range_low``,
``range_length`` bits, big-endian) — exactly the inverse of
:class:`pypdfbox.jbig2.decoder.huffman.value_node.ValueNode.decode`.

A constructed stream is validated against the bundled Java decoder
(``Jbig2SymbolDictProbe`` / ``Jbig2PageProbe``) *before* it is trusted as an
oracle fixture.
"""

from __future__ import annotations

from pypdfbox.jbig2.decoder.huffman.standard_tables import StandardTables

# JBIG2 file header magic ID (D.4.1).
FILE_HEADER_ID = bytes([0x97, 0x4A, 0x42, 0x32, 0x0D, 0x0A, 0x1A, 0x0A])


class BitWriter:
    """MSB-first bit accumulator matching ``ImageInputStream`` read order."""

    def __init__(self) -> None:
        self._bytes = bytearray()
        self._cur = 0
        self._nbits = 0

    def write_bit(self, bit: int) -> None:
        self._cur = (self._cur << 1) | (bit & 1)
        self._nbits += 1
        if self._nbits == 8:
            self._bytes.append(self._cur)
            self._cur = 0
            self._nbits = 0

    def write_bits(self, value: int, count: int) -> None:
        for i in range(count - 1, -1, -1):
            self.write_bit((value >> i) & 1)

    def write_byte(self, value: int) -> None:
        self.write_bits(value & 0xFF, 8)

    def align(self) -> None:
        """Pad the current byte with zero bits (byte alignment / skip_bits)."""
        if self._nbits != 0:
            self._cur <<= 8 - self._nbits
            self._bytes.append(self._cur)
            self._cur = 0
            self._nbits = 0

    def to_bytes(self) -> bytes:
        self.align()
        return bytes(self._bytes)

    @property
    def bit_position(self) -> int:
        return len(self._bytes) * 8 + self._nbits


def _find_code(table_number: int, value: int):
    """Return the StandardTable code line whose range contains ``value``.

    Reuses the port's canonical prefix-code assignment so the emitted bits
    round-trip exactly through ``HuffmanTable.decode``.
    """
    table = StandardTables.get_table(table_number)
    # StandardTable stores its assigned codes on the tree; rebuild the flat
    # code list the same way StandardTable.__init__ does so we can pick the
    # line matching ``value`` and read its assigned ``.code``.
    from pypdfbox.jbig2.decoder.huffman.huffman_table import Code
    from pypdfbox.jbig2.decoder.huffman.standard_tables import _TABLES

    lines = []
    for sub in _TABLES[table_number - 1]:
        lines.append(
            Code(sub[0], sub[1], sub[2], len(sub) > 3)
        )
    # Assign canonical codes exactly as HuffmanTable._preprocess_codes does.
    table._preprocess_codes(lines)  # noqa: SLF001 - intentional reuse

    best = None
    for c in lines:
        if c.range_length < 0:
            continue  # OOB line
        if c.is_lower_range:
            # value = range_low - bits, bits in [0, 2^32) — only as fallback
            continue
        lo = c.range_low
        hi = c.range_low + ((1 << c.range_length) - 1 if c.range_length < 32 else (1 << 31))
        # Prefer the tightest (smallest range) matching line.
        if lo <= value <= hi and (best is None or c.range_length < best.range_length):
            best = c
    if best is None:
        raise ValueError(
            f"No standard-table-{table_number} line covers value {value}"
        )
    return best


def write_huffman(bw: BitWriter, table_number: int, value: int) -> None:
    """Emit ``value`` using standard Huffman table ``table_number``."""
    c = _find_code(table_number, value)
    bw.write_bits(c.code, c.prefix_length)
    if c.range_length > 0:
        bw.write_bits(value - c.range_low, c.range_length)


def write_huffman_oob(bw: BitWriter, table_number: int) -> None:
    """Emit the OOB code of standard Huffman table ``table_number``."""
    from pypdfbox.jbig2.decoder.huffman.huffman_table import Code
    from pypdfbox.jbig2.decoder.huffman.standard_tables import _TABLES

    table = StandardTables.get_table(table_number)
    lines = [Code(s[0], s[1], s[2], len(s) > 3) for s in _TABLES[table_number - 1]]
    table._preprocess_codes(lines)  # noqa: SLF001
    for c in lines:
        if c.range_length < 0:
            bw.write_bits(c.code, c.prefix_length)
            return
    raise ValueError(f"Table {table_number} has no OOB line")


def file_header(pages: int = 1, sequential: bool = True) -> bytes:
    """Build a 13-byte file header (known page count)."""
    bw = BitWriter()
    for b in FILE_HEADER_ID:
        bw.write_byte(b)
    # Header flag byte: bits 3-7 reserved 0, bit2 ext-template 0,
    # bit1 pages-unknown 0 (we supply a count), bit0 organisation.
    flag = 0
    if not sequential:
        flag = 0  # organisation bit 0 == 0 means RANDOM? See note below.
    # bit1 (pages-unknown): we write KNOWN so the bit must be 0.
    # bit0 (organisation): SEQUENTIAL == 1.
    organisation_bit = 1 if sequential else 0
    flag = organisation_bit  # bit0
    bw.write_byte(flag)
    # Number of pages (4 bytes), present because pages-unknown == 0.
    bw.write_bits(pages, 32)
    return bw.to_bytes()


def segment_header(
    segment_nr: int,
    segment_type: int,
    referred_to: list[int],
    page_association: int,
    data_length: int,
) -> bytes:
    """Build a segment header (7.2). Short referred-to format only (<= 4)."""
    bw = BitWriter()
    # 7.2.2 segment number (4 bytes).
    bw.write_bits(segment_nr, 32)
    # 7.2.3 flags: bit7 retain 0, bit6 page-assoc-size 0 (1 byte), bits5-0 type.
    bw.write_bit(0)
    bw.write_bit(0)
    bw.write_bits(segment_type, 6)
    # 7.2.4 referred-to count + retain bits (short format: count<=4, 1 byte).
    count = len(referred_to)
    if count > 4:
        raise ValueError("long referred-to format not supported by helper")
    bw.write_bits(count, 3)
    bw.write_bits(0, 5)  # retain bits
    # 7.2.5 referred-to segment numbers (1 byte each when segment_nr <= 256).
    if segment_nr > 256:
        raise ValueError("multi-byte referred-to numbers not supported by helper")
    for rt in referred_to:
        bw.write_byte(rt)
    # 7.2.6 page association (1 byte, page-assoc-size == 0).
    bw.write_byte(page_association)
    # 7.2.7 segment data length (4 bytes).
    bw.write_bits(data_length, 32)
    return bw.to_bytes()


def page_info_segment_data(width: int, height: int) -> bytes:
    """Build a page-information segment data part (7.4.8). 19 bytes."""
    bw = BitWriter()
    bw.write_bits(width, 32)
    bw.write_bits(height, 32)
    bw.write_bits(0, 32)  # x resolution
    bw.write_bits(0, 32)  # y resolution
    bw.write_byte(0)  # flags: default pixel 0, OR operator, etc.
    bw.write_bits(0, 16)  # striping info
    return bw.to_bytes()


def end_of_page_segment_data() -> bytes:
    return b""


def region_segment_info(
    width: int, height: int, x: int = 0, y: int = 0, comb_op: int = 0
) -> bytes:
    """Region segment information field (7.4.1). 17 bytes."""
    bw = BitWriter()
    bw.write_bits(width, 32)
    bw.write_bits(height, 32)
    bw.write_bits(x, 32)
    bw.write_bits(y, 32)
    bw.write_bits(0, 5)  # reserved
    bw.write_bits(comb_op & 0x7, 3)
    return bw.to_bytes()


def write_symbol_id_code_lengths(
    bw: BitWriter, symbol_code_lengths: list[int]
) -> None:
    """Emit the SBSYMCODES run-code preamble (7.4.3.1.7 / fig in TextRegion).

    ``symbol_code_lengths[i]`` is the code length assigned to symbol ``i``.
    We use a trivial run-code table: every distinct length value ``v`` present
    is given a 1-bit-or-more run code, and lengths are emitted one at a time
    (no run compression, code values < 32). All lengths must be in [1, 31].
    """
    from pypdfbox.jbig2.decoder.huffman.fixed_size_table import FixedSizeTable
    from pypdfbox.jbig2.decoder.huffman.huffman_table import Code

    distinct = sorted(set(symbol_code_lengths))
    if any(v < 1 or v > 31 for v in distinct):
        raise ValueError("symbol code lengths must be in [1, 31]")
    # Build a run-code table over run-code values == the distinct lengths.
    # Assign each distinct length value a prefix length; use enough bits to be
    # an unambiguous prefix code. We give them all the same prefix length L
    # where 2^L >= len(distinct).
    import math

    n_distinct = len(distinct)
    pref_len = max(1, math.ceil(math.log2(n_distinct))) if n_distinct > 1 else 1
    # run-code table: 35 entries; entry index == run-code value (the length).
    pref_by_value = {v: pref_len for v in distinct}
    # Emit 35 nibbles.
    for i in range(35):
        bw.write_bits(pref_by_value.get(i, 0), 4)
    # Compute the canonical codes the decoder will build for those run codes.
    run_codes = [Code(pref_by_value[v], 0, v, False) for v in distinct]
    rt = FixedSizeTable(run_codes)  # assigns canonical .code
    code_for_value = {c.range_low: c for c in run_codes}
    # Now emit one run code per symbol's length (no run compression).
    for length in symbol_code_lengths:
        c = code_for_value[length]
        bw.write_bits(c.code, c.prefix_length)
    bw.align()  # 6) skip remaining bits in last byte
    # rt is unused after assignment but kept to mirror decoder construction.
    del rt


def symbol_code_table(symbol_code_lengths: list[int]):
    """Return the FixedSizeTable the decoder builds for symbol IDs.

    Lets the encoder look up each symbol id's canonical prefix bits.
    """
    from pypdfbox.jbig2.decoder.huffman.fixed_size_table import FixedSizeTable
    from pypdfbox.jbig2.decoder.huffman.huffman_table import Code

    codes = [
        Code(length, 0, i, False)
        for i, length in enumerate(symbol_code_lengths)
        if length > 0
    ]
    FixedSizeTable(codes)  # assigns canonical .code in place
    return {c.range_low: c for c in codes}


# ---------------------------------------------------------------------------
# High-level fixture builders (verified bit-exact vs the bundled 3.0.7 jar via
# Jbig2SymbolDictProbe / Jbig2PageProbe / Jbig2SymbolDictByNrProbe). See
# tests/jbig2/segments/oracle/test_huffman_refinement_fixtures_wave1503.py.
# ---------------------------------------------------------------------------


def huffman_sd_data(symbols: list[tuple[int, int]]) -> bytes:
    """SDHUFF=1, SDREFAGG=0 symbol dictionary data part.

    All symbols share one height class (height == symbols[0][1]); the collective
    bitmap is uncompressed (BMSIZE==0). Sets the top-left pixel of each symbol
    and the bottom-right pixel of the last so the decoded bytes are non-trivial.
    """
    bw = BitWriter()
    bw.write_bits(1 << 0, 16)  # region flags: SDHUFF only
    n = len(symbols)
    bw.write_bits(n, 32)  # exported
    bw.write_bits(n, 32)  # new
    height = symbols[0][1]
    write_huffman(bw, 4, height)  # HCDH (B4)
    prev_w = 0
    total_width = 0
    for (w, _h) in symbols:
        write_huffman(bw, 2, w - prev_w)  # DW (B2)
        prev_w = w
        total_width += w
    write_huffman_oob(bw, 2)  # OOB ends height class
    write_huffman(bw, 1, 0)  # BMSIZE (B1) == 0 -> uncompressed
    bw.align()
    stride = (total_width + 7) // 8
    rows = [bytearray(stride) for _ in range(height)]
    col = 0
    for (w, _h) in symbols:
        rows[0][col // 8] |= 0x80 >> (col % 8)
        last = col + w - 1
        rows[height - 1][last // 8] |= 0x80 >> (last % 8)
        col += w
    for r in rows:
        for b in r:
            bw.write_byte(b)
    bw.align()
    write_huffman(bw, 1, 0)  # export run 0 (none unexported)
    write_huffman(bw, 1, n)  # export run n (all exported)
    return bw.to_bytes()


def huffman_text_region_data(
    width: int,
    height: int,
    symbols: list[tuple[int, int]],
    placements: list[tuple[int, int, int]],
) -> bytes:
    """SBHUFF=1, REFINE=0 text-region data; one strip at t==0, refCorner TL."""
    n = len(symbols)
    bw = BitWriter()
    for b in region_segment_info(width, height):
        bw.write_byte(b)
    flags = (1 << 0) | (1 << 4)  # SBHUFF=1, refCorner=TOPLEFT(1)
    bw.write_bits(flags, 16)
    bw.write_bits(0, 16)  # huffman flags: all selections 0
    bw.write_bits(len(placements), 32)  # SBNUMINSTANCES
    code_lengths = [1] * n if n > 1 else [1]
    write_symbol_id_code_lengths(bw, code_lengths)
    code_map = symbol_code_table(code_lengths)
    write_huffman(bw, 11, 1)  # STRIPT (B11) value 1 -> base -1
    write_huffman(bw, 11, 1)  # DT (B11) 1 -> stripT 0
    first_s = placements[0][1]
    write_huffman(bw, 6, first_s)  # DfS (B6)
    c0 = code_map[placements[0][0]]
    bw.write_bits(c0.code, c0.prefix_length)
    prev_s = first_s
    prev_sym_w = symbols[placements[0][0]][0]
    for (sid, s, _t) in placements[1:]:
        ids = s - (prev_s + prev_sym_w - 1)
        write_huffman(bw, 8, ids)  # IdS (B8)
        c = code_map[sid]
        bw.write_bits(c.code, c.prefix_length)
        prev_s = s
        prev_sym_w = symbols[sid][0]
    write_huffman_oob(bw, 8)  # OOB ends strip
    bw.align()
    return bw.to_bytes()


def huffman_text_region_refine_data(
    width: int, height: int, symbols: list[tuple[int, int]], refine_bytes: int
) -> bytes:
    """SBHUFF=1, REFINE=1 text region: one refined instance (RDW/RDH/RDX/RDY=0).

    SBRTEMPLATE=1 (no refinement AT pixels). ``refine_bytes`` zero bytes are
    supplied for the refinement bitmap; SBHUFFRSIZE selects B1 for symInRefSize.
    """
    n = len(symbols)
    bw = BitWriter()
    for b in region_segment_info(width, height):
        bw.write_byte(b)
    flags = (1 << 0) | (1 << 1) | (1 << 4) | (1 << 15)  # SBHUFF,REFINE,TL,SBRT=1
    bw.write_bits(flags, 16)
    bw.write_bits(0, 16)  # huffman flags all 0
    bw.write_bits(1, 32)  # SBNUMINSTANCES = 1
    code_lengths = [1] * n if n > 1 else [1]
    write_symbol_id_code_lengths(bw, code_lengths)
    code_map = symbol_code_table(code_lengths)
    write_huffman(bw, 11, 1)
    write_huffman(bw, 11, 1)
    write_huffman(bw, 6, 0)  # DfS
    c0 = code_map[0]
    bw.write_bits(c0.code, c0.prefix_length)
    bw.write_bit(1)  # RI = 1 (refined)
    write_huffman(bw, 14, 0)  # RDW (B14)
    write_huffman(bw, 14, 0)  # RDH
    write_huffman(bw, 14, 0)  # RDX
    write_huffman(bw, 14, 0)  # RDY
    write_huffman(bw, 1, refine_bytes)  # symInRefSize (B1)
    bw.align()
    for _ in range(refine_bytes):
        bw.write_byte(0)
    write_huffman_oob(bw, 8)  # OOB ends strip
    bw.align()
    return bw.to_bytes()


def huffman_sd_refagg_aggregate_data(
    new_w: int, new_h: int, n_inst: int = 2
) -> bytes:
    """SDHUFF=1, SDREFAGG=1 dictionary using the aggregate route (n_inst>1).

    One new symbol decoded through a one-strip TextRegion of ``n_inst``
    instances (r==0) of imported symbol 0. SDRTEMPLATE=1. Refers to a base
    symbol dictionary providing the imported symbol. Includes a 4-byte trailing
    pad so the bundled jar (MemoryCacheImageInputStream throws EOF rather than
    zero-padding) has slack for the final Huffman export-flag reads.
    """
    bw = BitWriter()
    bw.write_bits((1 << 0) | (1 << 1) | (1 << 12), 16)  # SDHUFF,SDREFAGG,SDRT=1
    bw.write_bits(2, 32)  # exported (imported + new)
    bw.write_bits(1, 32)  # new
    write_huffman(bw, 4, new_h)  # HCDH
    write_huffman(bw, 2, new_w)  # DW
    write_huffman(bw, 1, n_inst)  # naggInst (B1) > 1 -> TextRegion
    write_huffman(bw, 11, 1)  # STRIPT
    write_huffman(bw, 11, 1)  # DT
    write_huffman(bw, 6, 0)  # DfS
    bw.write_bit(0)  # ID symbol 0
    bw.write_bit(0)  # RI r=0
    for _ in range(n_inst - 1):
        write_huffman(bw, 8, 0)  # IdS
        bw.write_bit(0)  # ID symbol 0
        bw.write_bit(0)  # RI r=0
    write_huffman_oob(bw, 8)  # OOB ends strip
    bw.align()
    write_huffman(bw, 1, 0)  # export run 0
    write_huffman(bw, 1, 2)  # export run 2 (export both)
    return bw.to_bytes() + b"\x00\x00\x00\x00"


def assemble(segments: list[tuple[int, int, list[int], int, bytes]], pages: int = 1) -> bytes:
    """Assemble a standalone JBIG2 stream from (nr, type, refs, page, data).

    Prepends a 13-byte file header (known page count, SEQUENTIAL).
    """
    parts = [file_header(pages, True)]
    for (nr, stype, refs, page, data) in segments:
        parts.append(segment_header(nr, stype, refs, page, len(data)))
        parts.append(data)
    return b"".join(parts)
