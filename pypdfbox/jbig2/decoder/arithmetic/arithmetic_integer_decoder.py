"""The arithmetic integer decoder, ISO/IEC 14492:2001 (Annex A).

Port of ``org.apache.pdfbox.jbig2.decoder.arithmetic.ArithmeticIntegerDecoder``.
Implements the IAx integer decoding procedure (A.2) and the IAID symbol-ID
decoding procedure (A.3).
"""

from __future__ import annotations

from pypdfbox.jbig2.decoder.arithmetic.arithmetic_decoder import ArithmeticDecoder
from pypdfbox.jbig2.decoder.arithmetic.cx import CX

# Java ``Long.MAX_VALUE`` — returned by ``decode`` for the out-of-band (OOB)
# value defined by the integer arithmetic decoding procedure.
LONG_MAX_VALUE = 0x7FFFFFFFFFFFFFFF


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

        for _i in range(sym_code_len):
            cx_iaid.set_index(prev & mask)
            prev = (prev << 1) | self.decoder.decode(cx_iaid)

        # A.3 3) & 4)
        return prev - (1 << sym_code_len)
