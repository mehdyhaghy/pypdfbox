"""Minimal MQ-arithmetic ENCODER for JBIG2 parity-test fixture construction.

This is a *test helper*, not a port of any upstream class — Apache PDFBox only
*decodes* JBIG2, so it ships no arithmetic encoder. JBIG2's arithmetic coder is
the MQ coder of ITU-T Rec. T.88 Annex E (identical to the JPEG2000 MQ coder).
The decoder side is the production
:class:`pypdfbox.jbig2.decoder.arithmetic.ArithmeticDecoder`; this module is the
symmetric ENCODER (T.88 E.3: INITENC / ENCODE / CODE0 / CODE1 / CODELPS /
CODEMPS / RENORME / BYTEOUT / FLUSH) so a test can produce arithmetic-coded
JBIG2 bodies (generic-region bitmaps, IAx integers, IAID symbol ids) that
``ArithmeticDecoder`` — and the bundled Java decoder — read back bit-exact.

The probability-estimation state table (Qe, NMPS, NLPS, SWITCH) is *shared*
between encoder and decoder; this module imports the production ``QE`` table from
:mod:`pypdfbox.jbig2.decoder.arithmetic.arithmetic_decoder` so the two sides can
never drift.

Context state is held in a :class:`Cx` (mirroring the production ``CX``: an index
plus per-state probability-index ``i`` and MPS arrays). The encoder mutates the
selected context exactly the way the decoder does (CODELPS/CODEMPS adjust ``i``
and conditionally toggle MPS), so encode and decode walk the identical state
machine.

Validated by round-trip against the production decoder (see
``tests/jbig2/helpers/test_mq_encoder.py``).
"""

from __future__ import annotations

from pypdfbox.jbig2.decoder.arithmetic.arithmetic_decoder import QE

# Java ``Long.MAX_VALUE`` sentinel for the OOB integer value (mirror of the
# decoder's ``LONG_MAX_VALUE``).
OOB = 0x7FFFFFFFFFFFFFFF


class Cx:
    """Encoder-side arithmetic context (mirror of the decoder's ``CX``).

    ``size`` per-state slots; ``index`` selects the active slot. ``_i`` holds the
    Qe-table row index (0-46) and ``_mps`` the most-probable-symbol bit, exactly
    as the decoder's ``cx`` / ``mps`` arrays.
    """

    def __init__(self, size: int, index: int = 0) -> None:
        self.index = index
        self._i = bytearray(size)
        self._mps = bytearray(size)

    def set_index(self, index: int) -> None:
        self.index = index

    def i(self) -> int:
        return self._i[self.index] & 0x7F

    def set_i(self, value: int) -> None:
        self._i[self.index] = value & 0x7F

    def mps(self) -> int:
        return self._mps[self.index]

    def toggle_mps(self) -> None:
        self._mps[self.index] ^= 1

    def copy(self) -> Cx:
        """Return a deep copy (mirror of the decoder's ``CX.copy``).

        Used to model coding-context reuse across symbol dictionaries: a
        context-using SD adopts ``base.cx.copy()`` as the starting bitmap
        context, so the encoder must continue from a copy of the base
        encoder's bitmap ``Cx`` after the base body was encoded.
        """
        result = Cx(len(self._i), self.index)
        result._i[:] = self._i
        result._mps[:] = self._mps
        return result


class MQEncoder:
    """The MQ arithmetic ENCODER (ITU-T Rec. T.88 Annex E.3).

    Register names follow the spec: ``a`` (interval), ``c`` (code), ``ct``
    (counter), ``bp`` (byte pointer into the output buffer), ``b`` (current
    output byte). The decoder this pairs with is
    ``ArithmeticDecoder._byte_in`` / ``decode``; the byte-stuffing convention
    (a 0xFF byte forces the next byte to carry only 7 code bits) matches that
    decoder's ``b == 0xFF`` branch.
    """

    def __init__(self) -> None:
        self._out = bytearray()
        # INITENC (jbig2enc jbig2arith.cc): a, c, ct, byte pointer bp and the
        # pending byte b. ``bp == -1`` means no byte has been emitted yet; the
        # pending ``b`` is committed to the stream by the next BYTEOUT/FLUSH.
        self.a = 0x8000
        self.c = 0
        self.ct = 12
        self.bp = -1
        self.b = 0

    def _emit(self) -> None:
        self._out.append(self.b & 0xFF)

    def encode(self, cx: Cx, d: int) -> None:
        """ENCODE (T.88 Figure E.6): code decision ``d`` under context ``cx``."""
        i = cx.i()
        qe = QE[i][0]
        if d != cx.mps():
            self._code_lps(cx, i, qe)
        else:
            self._code_mps(cx, i, qe)

    def _code_mps(self, cx: Cx, i: int, qe: int) -> None:
        # MPS branch of ENCODE (jbig2arith.cc): on conditional exchange the LPS
        # interval is coded by keeping A = Qe; otherwise C += Qe.
        self.a -= qe
        if (self.a & 0x8000) == 0:
            if self.a < qe:
                self.a = qe
            else:
                self.c += qe
            cx.set_i(QE[i][1])  # NMPS
            self._renorm_e()
        else:
            self.c += qe

    def _code_lps(self, cx: Cx, i: int, qe: int) -> None:
        # CODELPS (jbig2arith.cc): A -= Qe; if A < Qe code on top (C += Qe) else
        # A = Qe. The SWITCH bit conditionally flips the context MPS; transition
        # to NLPS. (The decoder's LPS_EXCHANGE inverts this.)
        self.a -= qe
        if self.a < qe:
            self.c += qe
        else:
            self.a = qe
        if QE[i][3] == 1:  # SWITCH
            cx.toggle_mps()
        cx.set_i(QE[i][2])  # NLPS
        self._renorm_e()

    def _renorm_e(self) -> None:
        # RENORME (jbig2arith.cc).
        while True:
            self.a = (self.a << 1) & 0xFFFFFFFF
            self.c = (self.c << 1) & 0xFFFFFFFF
            self.ct -= 1
            if self.ct == 0:
                self._byte_out()
            if (self.a & 0x8000) != 0:
                break

    def _byte_out(self) -> None:
        # BYTEOUT (jbig2arith.cc ``byteout``).
        if self.b == 0xFF:
            self._rblock()
        elif self.c < 0x8000000:
            self._lblock()
        else:
            self.b = (self.b + 1) & 0xFF
            if self.b != 0xFF:
                self._lblock()
            else:
                self.c &= 0x7FFFFFF
                self._rblock()

    def _rblock(self) -> None:
        if self.bp >= 0:
            self._emit()
        self.b = (self.c >> 20) & 0xFF
        self.bp += 1
        self.c &= 0xFFFFF
        self.ct = 7

    def _lblock(self) -> None:
        if self.bp >= 0:
            self._emit()
        self.b = (self.c >> 19) & 0xFF
        self.bp += 1
        self.c &= 0x7FFFF
        self.ct = 8

    def flush(self) -> bytes:
        """FLUSH (jbig2arith.cc ``encode_final``): final bits + terminator."""
        temp_c = (self.c + self.a) & 0xFFFFFFFF
        self.c |= 0xFFFF
        if self.c >= temp_c:
            self.c -= 0x8000
        self.c = (self.c << self.ct) & 0xFFFFFFFF
        self._byte_out()
        self.c = (self.c << self.ct) & 0xFFFFFFFF
        self._byte_out()
        self._emit()  # commit the last pending byte
        if self.b != 0xFF:
            self.b = 0xFF
            self._emit()
        self.b = 0xAC
        self._emit()
        return bytes(self._out)


# Range buckets of the integer arithmetic decoding procedure (Annex A.2), in the
# order the decoder's prefix bits select them. Each entry is
# ``(prefix_bits, n_magnitude_bits, offset)`` where ``prefix_bits`` is the unary
# selector emitted MSB-first via the IAx context (the decoder reads them as the
# sequence of ``d`` decisions before the magnitude loop).
_IAX_BUCKETS = (
    ((0,), 2, 0),
    ((1, 0), 4, 4),
    ((1, 1, 0), 6, 20),
    ((1, 1, 1, 0), 8, 84),
    ((1, 1, 1, 1, 0), 12, 340),
    ((1, 1, 1, 1, 1), 32, 4436),
)


def _set_prev(prev: int, bit: int) -> int:
    """Mirror ``ArithmeticIntegerDecoder._set_prev``."""
    if prev < 256:  # noqa: SIM108
        prev = ((prev << 1) | bit) & 0x1FF
    else:
        prev = ((((prev << 1) | bit) & 511) | 256) & 0x1FF
    return prev


class ArithmeticIntegerEncoder:
    """IAx / IAID integer ENCODER — the inverse of ``ArithmeticIntegerDecoder``.

    Each instance is bound to one :class:`Cx` per logical integer context (IADH,
    IADW, IAEX, IAAI, IAID, ...), exactly as the decoder allocates one ``CX`` per
    context. ``encode`` writes an integer value; ``encode_iaid`` writes a symbol
    id of ``sym_code_len`` bits.
    """

    def __init__(self, encoder: MQEncoder) -> None:
        self.encoder = encoder

    def encode(self, cx: Cx, value: int) -> None:
        """Encode ``value`` (or :data:`OOB`) under integer context ``cx`` (A.2)."""
        if value == OOB:
            s = 1
            magnitude = 0
        elif value < 0:
            s = 1
            magnitude = -value
        else:
            s = 0
            magnitude = value

        bucket = None
        for prefix_bits, n_bits, offset in _IAX_BUCKETS:
            top = offset + ((1 << n_bits) - 1)
            if magnitude <= top:
                bucket = (prefix_bits, n_bits, offset)
                break
        if bucket is None:
            raise ValueError(f"value {value} out of IAx range")
        prefix_bits, n_bits, offset = bucket
        v = magnitude - offset

        prev = 1
        # Sign bit first.
        cx.set_index(prev & 0x1FF)
        self.encoder.encode(cx, s)
        prev = _set_prev(prev, s)
        # Range-selector prefix bits.
        for bit in prefix_bits:
            cx.set_index(prev & 0x1FF)
            self.encoder.encode(cx, bit)
            prev = _set_prev(prev, bit)
        # Magnitude bits, MSB-first.
        for k in range(n_bits - 1, -1, -1):
            bit = (v >> k) & 1
            cx.set_index(prev & 0x1FF)
            self.encoder.encode(cx, bit)
            prev = _set_prev(prev, bit)

    def encode_iaid(self, cx: Cx, value: int, sym_code_len: int) -> None:
        """Encode symbol id ``value`` (A.3), mirroring ``decode_iaid``."""
        prev = 1
        mask = (1 << sym_code_len) - 1
        for k in range(sym_code_len - 1, -1, -1):
            bit = (value >> k) & 1
            cx.set_index(prev & mask)
            self.encoder.encode(cx, bit)
            prev = (prev << 1) | bit


_MASK16 = 0xFFFF


def encode_generic_region_template0(
    encoder: MQEncoder, cx: Cx, rows: list[list[int]], width: int, height: int
) -> None:
    """Encode a generic-region bitmap with template 0, nominal AT, no TPGDON.

    ``rows[y][x]`` is the pixel bit. The per-pixel arithmetic context is computed
    *identically* to ``GenericRegion._decode_template0a`` (the production
    decoder), so the produced bits decode back to the same bitmap and the CX
    state evolves the same way — letting the encoder feed the bundled Java
    decoder and pypdfbox alike. The bitmap is built up incrementally exactly as
    the decoder builds it, so neighbour reads see only already-coded pixels.

    Mirrors the decoder's byte-oriented line registers (``line1`` / ``line2``)
    and 16-bit ``context`` register.
    """
    row_stride = (width + 7) // 8
    padded_width = (width + 7) & -8
    # Build the bitmap byte-store as the decoder does (set_byte per finished byte).
    store = bytearray(row_stride * height)

    def get_byte(idx: int) -> int:
        if idx < 0 or idx >= len(store):
            return 0
        return store[idx]

    for line_number in range(height):
        byte_index = line_number * row_stride
        idx = byte_index - row_stride

        line1 = get_byte(idx) if line_number >= 1 else 0
        line2 = (get_byte(idx - row_stride) << 6) if line_number >= 2 else 0

        context = (line1 & 0xF0) | (line2 & 0x3800)

        x = 0
        while x < padded_width:
            result = 0
            next_byte = x + 8
            minor_width = 8 if width - x > 8 else width - x

            if line_number > 0:
                line1 = (line1 << 8) | (
                    get_byte(idx + 1) if next_byte < width else 0
                )
            if line_number > 1:
                line2 = (line2 << 8) | (
                    (get_byte(idx - row_stride + 1) << 6) if next_byte < width else 0
                )

            for minor_x in range(minor_width):
                to_shift = 7 - minor_x
                cx.set_index(context)
                bit = rows[line_number][x + minor_x]
                encoder.encode(cx, bit)
                result |= bit << to_shift
                context = (
                    ((context & 0x7BF7) << 1)
                    | bit
                    | ((line1 >> to_shift) & 0x10)
                    | ((line2 >> to_shift) & 0x800)
                ) & _MASK16

            store[byte_index] = result
            byte_index += 1
            idx += 1
            x = next_byte


def _pixel_safe(rows: list[list[int]], width: int, height: int, x: int, y: int) -> int:
    """Mirror ``_get_pixel_safe`` (§6.3.5.2 out-of-bounds rule: outside == 0)."""
    if x < 0 or y < 0 or x >= width or y >= height:
        return 0
    return rows[y][x]


def encode_refinement_region_template1(
    encoder: MQEncoder,
    cx: Cx,
    target_rows: list[list[int]],
    width: int,
    height: int,
    reference_rows: list[list[int]],
    ref_width: int,
    ref_height: int,
    reference_dx: int,
    reference_dy: int,
) -> None:
    """Encode a generic-refinement-region bitmap with GRTEMPLATE 1, TPGRON off.

    The inverse of ``GenericRefinementRegionDecodingProcedure`` for the
    template-1, non-TPGR path (``_decode_line_explicit_t1`` + ``_build_context_t1``,
    the per-pixel route the SD single-instance refinement and the SD aggregate
    TextRegion use for ``sdr_template == 1`` / ``sbr_template == 1``). Pixels are
    encoded in row-major order; each pixel's context is formed from the
    *already-encoded* region pixels (``target_rows`` built up incrementally) and
    the static reference bitmap, identical to the decoder, so the produced bits
    decode back to ``target_rows`` and the CX state evolves the same way.
    """
    # Build the region incrementally so neighbour reads see only coded pixels.
    region = [[0] * width for _ in range(height)]

    def region_bit(x: int, y: int) -> int:
        return _pixel_safe(region, width, height, x, y)

    def reference_bit(x: int, y: int) -> int:
        return _pixel_safe(
            reference_rows, ref_width, ref_height, x - reference_dx, y - reference_dy
        )

    def build_context_t1(x: int, y: int) -> int:
        return (
            (region_bit(x - 1, y - 1) << 9)
            | (region_bit(x, y - 1) << 8)
            | (region_bit(x + 1, y - 1) << 7)
            | (region_bit(x - 1, y) << 6)
            | (reference_bit(x, y - 1) << 5)
            | (reference_bit(x - 1, y) << 4)
            | (reference_bit(x, y) << 3)
            | (reference_bit(x + 1, y) << 2)
            | (reference_bit(x, y + 1) << 1)
            | (reference_bit(x + 1, y + 1))
        )

    for y in range(height):
        for x in range(width):
            cx.set_index(build_context_t1(x, y))
            bit = target_rows[y][x]
            encoder.encode(cx, bit)
            region[y][x] = bit
