"""Live differential oracle for the JBIG2 MQ arithmetic decoder.

Drives the upstream Apache PDFBox ``ArithmeticDecoder`` (+ ``CX``) via
``oracle/probes/ArithDecodeProbe.java`` on a fixed input byte array and asserts
that pypdfbox's ``ArithmeticDecoder`` produces the IDENTICAL decoded bit
sequence. This is the gold-standard parity check for the bit-exact MQ-coder
state machine (Qe table, MPS/LPS exchange, RENORMD, BYTEIN, register masking).
"""

from __future__ import annotations

import pytest

from pypdfbox.jbig2.decoder.arithmetic.arithmetic_decoder import ArithmeticDecoder
from pypdfbox.jbig2.decoder.arithmetic.cx import CX
from tests.jbig2.decoder.arithmetic.test_arithmetic_decoder import MemoryImageInputStream
from tests.oracle.harness import requires_oracle, run_probe_text


def _py_decode(data: bytes, nbits: int, *, ctx_size: int, index: int, cycle: bool) -> str:
    iis = MemoryImageInputStream(data)
    decoder = ArithmeticDecoder(iis)
    cx = CX(ctx_size, index)
    bits = []
    for i in range(nbits):
        cx.set_index(i % ctx_size if cycle else index)
        bits.append(str(decoder.decode(cx)))
    return "".join(bits)


# (hexbytes, nbits, ctx_size, index, cycle)
_CASES = [
    ("84c73b00", 24, 512, 0, False),
    ("84c73b00ff12", 40, 512, 0, True),
    ("0000000000000000", 32, 512, 0, False),
    ("ffffffffffffffff", 32, 512, 0, False),
    ("ffac1234", 20, 512, 0, False),
    ("deadbeefcafebabe", 48, 512, 5, False),
    ("deadbeefcafebabe", 48, 256, 0, True),
    ("0102040810204080", 36, 512, 0, True),
    ("55aa55aa55aa", 30, 512, 1, False),
    ("00ff00ff00ff00ff", 40, 512, 0, True),
]


@requires_oracle
@pytest.mark.parametrize(
    ("hexbytes", "nbits", "ctx_size", "index", "cycle"),
    _CASES,
    ids=[f"{h}-{n}-{'cyc' if c else f'idx{ix}'}" for (h, n, _s, ix, c) in _CASES],
)
def test_arithmetic_decoder_matches_pdfbox(hexbytes, nbits, ctx_size, index, cycle):
    args = [hexbytes, str(nbits), str(ctx_size), str(index)]
    if cycle:
        args.append("cycle")
    java_bits = run_probe_text("ArithDecodeProbe", *args).strip()

    data = bytes.fromhex(hexbytes)
    py_bits = _py_decode(data, nbits, ctx_size=ctx_size, index=index, cycle=cycle)

    assert py_bits == java_bits
    assert len(py_bits) == nbits
