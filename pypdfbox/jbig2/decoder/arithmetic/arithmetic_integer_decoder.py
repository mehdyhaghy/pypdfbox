"""The arithmetic integer decoder, ISO/IEC 14492:2001 (Annex A).

Port of ``org.apache.pdfbox.jbig2.decoder.arithmetic.ArithmeticIntegerDecoder``.
Implements the IAx integer decoding procedure (A.2) and the IAID symbol-ID
decoding procedure (A.3).
"""

from pypdfbox.jbig2.decoder.arithmetic.arithmetic_decoder import (
    QE_DECODE,
    RENORM_SHIFTS,
    ArithmeticDecoder,
)
from pypdfbox.jbig2.decoder.arithmetic.cx import CX

# Java ``Long.MAX_VALUE`` — returned by ``decode`` for the out-of-band (OOB)
# value defined by the integer arithmetic decoding procedure.
LONG_MAX_VALUE = 0x7FFFFFFFFFFFFFFF

_MASK32 = 0xFFFFFFFF

# (bits_to_read, offset) selected by the first 0 among the prefix bits
# (A.2 step 3, Table A.1): the n-th prefix bit being 0 selects row n - 1.
_PREFIX_RANGES = ((2, 0), (4, 4), (6, 20), (8, 84), (12, 340))


class ArithmeticIntegerDecoder:
    """The IAx / IAID integer arithmetic decoder (Annex A)."""

    def __init__(self, decoder: ArithmeticDecoder) -> None:
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
        #
        # The decisions are decoded in the upstream order (sign S, then up to
        # five prefix bits, then the value bits) by a single loop with the MQ
        # DECODE procedure of ArithmeticDecoder.decode inlined; the decoder
        # registers live in locals and are written back on return.
        if cx_iax is None:
            cx_iax = CX(512, 1)

        dec = self.decoder
        if type(dec) is not ArithmeticDecoder or type(cx_iax) is not CX:
            return self._decode_by_calls(cx_iax)
        cx_arr = cx_iax._cx
        mps_arr = cx_iax._mps
        qe_table = QE_DECODE
        renorm_shifts = RENORM_SHIFTS
        a = dec.a
        c = dec.c
        ct = dec.ct

        prev = 1
        v = 0
        s = -1
        prefix_bits = 0
        remaining = -1
        offset = 0

        while True:
            index = prev & 0x1FF
            # Inlined ArithmeticDecoder.decode (E.3.2).
            row = qe_table[cx_arr[index] & 0x7F]
            qe_value = row[0]
            a -= qe_value
            if c < row[4]:
                # LPS_EXCHANGE
                mps = mps_arr[index]
                if a < qe_value:
                    cx_arr[index] = row[1]
                    d = mps
                else:
                    if row[3] == 1:
                        mps_arr[index] = mps ^ 1
                    cx_arr[index] = row[2]
                    d = 1 - mps
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
                c -= row[4]
                if a & 0x8000:
                    d = mps_arr[index]
                else:
                    # MPS_EXCHANGE
                    mps = mps_arr[index]
                    if a < qe_value:
                        if row[3] == 1:
                            mps_arr[index] = mps ^ 1
                        cx_arr[index] = row[2]
                        d = 1 - mps
                    else:
                        cx_arr[index] = row[1]
                        d = mps
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

            # _set_prev
            prev = (
                ((prev << 1) | d) & 0x1FF
                if prev < 256
                else ((((prev << 1) | d) & 511) | 256) & 0x1FF
            )

            if s < 0:
                s = d
            elif remaining < 0:
                prefix_bits += 1
                if d == 0:
                    remaining, offset = _PREFIX_RANGES[prefix_bits - 1]
                elif prefix_bits == 5:
                    remaining, offset = 32, 4436
            else:
                v = (v << 1) | d
                remaining -= 1
                if remaining == 0:
                    break

        dec.a = a
        dec.c = c
        dec.ct = ct
        cx_iax.index = index

        v += offset

        if s == 0:
            return v
        elif s == 1 and v > 0:
            return -v

        return LONG_MAX_VALUE

    def _decode_by_calls(self, cx_iax: CX) -> int:
        """A.2 driven through ``decoder.decode`` (any decoder object)."""
        prev = 1

        v = 0

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

        return LONG_MAX_VALUE

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

        dec = self.decoder
        if type(dec) is not ArithmeticDecoder or type(cx_iaid) is not CX:
            for _i in range(sym_code_len):
                cx_iaid.set_index(prev & mask)
                prev = (prev << 1) | dec.decode(cx_iaid)
        elif sym_code_len > 0:
            cx_arr = cx_iaid._cx
            mps_arr = cx_iaid._mps
            qe_table = QE_DECODE
            renorm_shifts = RENORM_SHIFTS
            a = dec.a
            c = dec.c
            ct = dec.ct
            for _i in range(sym_code_len):
                index = prev & mask
                # Inlined ArithmeticDecoder.decode (E.3.2).
                row = qe_table[cx_arr[index] & 0x7F]
                qe_value = row[0]
                a -= qe_value
                if c < row[4]:
                    # LPS_EXCHANGE
                    mps = mps_arr[index]
                    if a < qe_value:
                        cx_arr[index] = row[1]
                        d = mps
                    else:
                        if row[3] == 1:
                            mps_arr[index] = mps ^ 1
                        cx_arr[index] = row[2]
                        d = 1 - mps
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
                    c -= row[4]
                    if a & 0x8000:
                        d = mps_arr[index]
                    else:
                        # MPS_EXCHANGE
                        mps = mps_arr[index]
                        if a < qe_value:
                            if row[3] == 1:
                                mps_arr[index] = mps ^ 1
                            cx_arr[index] = row[2]
                            d = 1 - mps
                        else:
                            cx_arr[index] = row[1]
                            d = mps
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
                prev = (prev << 1) | d
            dec.a = a
            dec.c = c
            dec.ct = ct
            cx_iaid.index = index

        # A.3 3) & 4)
        return prev - (1 << sym_code_len)
