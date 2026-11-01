"""The MQ arithmetic decoder, described in ISO/IEC 14492:2001 in E.3.

Port of ``org.apache.pdfbox.jbig2.decoder.arithmetic.ArithmeticDecoder``.

This is a bit-exact state machine. The Java original relies on the bounded
width of ``int`` (the ``a`` register) and ``long`` (the ``c`` register). Python
integers are unbounded, so the ``c`` register is masked to 32 bits with
``& 0xFFFFFFFF`` exactly where the upstream applies ``& 0xffffffffL`` (after
``byteIn`` and at the end of ``renormalize``). The ``a`` register never grows
past 16 significant bits in practice — the ``a & 0x8000`` renormalisation
guard terminates the shift loop before it could overflow a Java ``int`` — but
it is masked to 32 bits on each left shift to faithfully mirror Java ``int``
wraparound and to keep the value bounded.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pypdfbox.jbig2.decoder.arithmetic.cx import CX

_MASK32 = 0xFFFFFFFF

# Probability-estimation table (Qe), 47 rows of {Qe, NMPS, NLPS, SWITCH},
# Table E.1 of ITU-T Rec. T.88. Ported exactly from upstream.
QE = (
    (0x5601, 1, 1, 1),
    (0x3401, 2, 6, 0),
    (0x1801, 3, 9, 0),
    (0x0AC1, 4, 12, 0),
    (0x0521, 5, 29, 0),
    (0x0221, 38, 33, 0),
    (0x5601, 7, 6, 1),
    (0x5401, 8, 14, 0),
    (0x4801, 9, 14, 0),
    (0x3801, 10, 14, 0),
    (0x3001, 11, 17, 0),
    (0x2401, 12, 18, 0),
    (0x1C01, 13, 20, 0),
    (0x1601, 29, 21, 0),
    (0x5601, 15, 14, 1),
    (0x5401, 16, 14, 0),
    (0x5101, 17, 15, 0),
    (0x4801, 18, 16, 0),
    (0x3801, 19, 17, 0),
    (0x3401, 20, 18, 0),
    (0x3001, 21, 19, 0),
    (0x2801, 22, 19, 0),
    (0x2401, 23, 20, 0),
    (0x2201, 24, 21, 0),
    (0x1C01, 25, 22, 0),
    (0x1801, 26, 23, 0),
    (0x1601, 27, 24, 0),
    (0x1401, 28, 25, 0),
    (0x1201, 29, 26, 0),
    (0x1101, 30, 27, 0),
    (0x0AC1, 31, 28, 0),
    (0x09C1, 32, 29, 0),
    (0x08A1, 33, 30, 0),
    (0x0521, 34, 31, 0),
    (0x0441, 35, 32, 0),
    (0x02A1, 36, 33, 0),
    (0x0221, 37, 34, 0),
    (0x0141, 38, 35, 0),
    (0x0111, 39, 36, 0),
    (0x0085, 40, 37, 0),
    (0x0049, 41, 38, 0),
    (0x0025, 42, 39, 0),
    (0x0015, 43, 40, 0),
    (0x0009, 44, 41, 0),
    (0x0005, 45, 42, 0),
    (0x0001, 45, 43, 0),
    (0x5601, 46, 46, 0),
)

# Decoder-side view of ``QE``: each row extended with ``Qe << 16``, so the
# ``(C >> 16) < Qe`` test of DECODE can be evaluated as ``C < (Qe << 16)``
# (equivalent for the non-negative C register) and ``C -= Qe << 16`` needs no
# shift.
QE_DECODE = tuple((qe, nmps, nlps, switch, qe << 16) for qe, nmps, nlps, switch in QE)

# RENORMD shift count for an A register value 1..0x7FFF: the number of left
# shifts until bit 15 (0x8000) is set. When CT covers that many shifts no
# BYTEIN can occur in between, so RENORMD reduces to one multi-bit shift of A
# and C (with C masked to 32 bits) and ``CT -= n``.
RENORM_SHIFTS = bytes([0] + [16 - a.bit_length() for a in range(1, 0x8000)])


class ArithmeticDecoder:
    """The MQ arithmetic decoder (ISO/IEC 14492:2001 E.3)."""

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

    def decode(self, cx: CX) -> int:
        """Decode one binary decision in context ``cx`` (E.3.2 DECODE).

        This is the ``DECODE`` / ``LPS_EXCHANGE`` / ``MPS_EXCHANGE`` /
        ``RENORMD`` procedure fused into one body with the registers held in
        locals and the context arrays indexed directly. It performs the same
        arithmetic in the same order as the separate helper methods below
        (which are kept for structural fidelity with upstream).
        """
        index = cx.index
        cx_arr = cx._cx
        row = QE_DECODE[cx_arr[index] & 0x7F]
        qe_value = row[0]

        a = self.a - qe_value
        c = self.c

        if c < row[4]:
            # LPS_EXCHANGE
            mps_arr = cx._mps
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
        else:
            c -= row[4]
            if a & 0x8000:
                self.a = a
                self.c = c
                return cx._mps[index]
            # MPS_EXCHANGE
            mps_arr = cx._mps
            mps = mps_arr[index]
            if a < qe_value:
                if row[3] == 1:
                    mps_arr[index] = mps ^ 1
                cx_arr[index] = row[2]
                d = 1 - mps
            else:
                cx_arr[index] = row[1]
                d = mps

        # RENORMD. ``a`` is below 0x8000 here, so the shifts stay within
        # 16 bits and the 32-bit mask on ``a`` is a no-op.
        ct = self.ct
        n = RENORM_SHIFTS[a]
        if ct >= n:
            a <<= n
            c = (c << n) & _MASK32
            ct -= n
        else:
            while True:
                if ct == 0:
                    self.c = c
                    self._byte_in()
                    c = self.c
                    ct = self.ct
                a <<= 1
                c = (c << 1) & _MASK32
                ct -= 1
                if a & 0x8000:
                    break

        self.a = a
        self.c = c
        self.ct = ct
        return d

    def _byte_in(self) -> None:
        iis = self.iis
        stream_pos = iis.get_stream_position()
        if stream_pos > self.stream_pos0:
            iis.seek(stream_pos - 1)

        b = iis.read()

        if b == 0xFF:
            self.b = b
            b1 = iis.read()
            if b1 > 0x8F:
                self.c = (self.c + 0xFF00) & _MASK32
                self.ct = 8
                iis.seek(iis.get_stream_position() - 2)
            else:
                self.c = (self.c + (b1 << 9)) & _MASK32
                self.ct = 7
        else:
            b = iis.read()
            self.b = b
            self.c = (self.c + (b << 8)) & _MASK32
            self.ct = 8

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

    def _mps_exchange(self, cx: CX, icx: int) -> int:
        mps = cx.mps()

        if self.a < QE[icx][0]:
            if QE[icx][3] == 1:
                cx.toggle_mps()

            cx.set_cx(QE[icx][2])
            return 1 - mps
        else:
            cx.set_cx(QE[icx][1])
            return mps

    def _lps_exchange(self, cx: CX, icx: int, qe_value: int) -> int:
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

    def get_a(self) -> int:
        return self.a

    def get_c(self) -> int:
        return self.c
