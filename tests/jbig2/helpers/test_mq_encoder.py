"""Standalone round-trip validation of the test-only MQ-arithmetic encoder.

Encodes known bit sequences under known contexts with
:class:`tests.jbig2.helpers.mq_encoder.MQEncoder`, then decodes the produced
bytes with the *production*
:class:`pypdfbox.jbig2.decoder.arithmetic.ArithmeticDecoder` and asserts the
decoded bits are identical. Because encoder and decoder share the single ``QE``
state table, a faithful encoder is exactly the inverse of the decoder; these
tests are the contract that pins that.
"""

from __future__ import annotations

import pytest

from pypdfbox.jbig2.decoder.arithmetic.arithmetic_decoder import ArithmeticDecoder
from pypdfbox.jbig2.decoder.arithmetic.arithmetic_integer_decoder import (
    LONG_MAX_VALUE,
    ArithmeticIntegerDecoder,
)
from pypdfbox.jbig2.decoder.arithmetic.cx import CX
from pypdfbox.jbig2.io.image_input_stream import ImageInputStream
from tests.jbig2.helpers.mq_encoder import (
    OOB,
    ArithmeticIntegerEncoder,
    Cx,
    MQEncoder,
)


def _roundtrip(bits: list[int], n_ctx: int = 1) -> list[int]:
    enc = MQEncoder()
    enc_cx = Cx(n_ctx, 0)
    for bit in bits:
        enc.encode(enc_cx, bit)
    data = enc.flush()

    dec = ArithmeticDecoder(ImageInputStream(data))
    dec_cx = CX(n_ctx, 0)
    out = []
    for _ in range(len(bits)):
        out.append(dec.decode(dec_cx))
    return out


def test_all_zeros():
    bits = [0] * 64
    assert _roundtrip(bits) == bits


def test_all_ones():
    bits = [1] * 64
    assert _roundtrip(bits) == bits


def test_alternating():
    bits = [i & 1 for i in range(100)]
    assert _roundtrip(bits) == bits


def test_single_bit_zero():
    assert _roundtrip([0]) == [0]


def test_single_bit_one():
    assert _roundtrip([1]) == [1]


@pytest.mark.parametrize("seed", [1, 7, 42, 1234, 99991])
def test_pseudorandom(seed):
    # Deterministic LCG so the test is reproducible without importing random.
    state = seed
    bits = []
    for _ in range(500):
        state = (1103515245 * state + 12345) & 0x7FFFFFFF
        bits.append((state >> 16) & 1)
    assert _roundtrip(bits) == bits


def test_multi_context():
    # Drive several contexts so NMPS/NLPS/SWITCH transitions all exercise.
    state = 2024
    bits = []
    indices = []
    for _ in range(800):
        state = (1103515245 * state + 12345) & 0x7FFFFFFF
        bits.append((state >> 16) & 1)
        indices.append((state >> 8) & 0x7)

    enc = MQEncoder()
    enc_cx = Cx(8, 0)
    for bit, idx in zip(bits, indices, strict=True):
        enc_cx.set_index(idx)
        enc.encode(enc_cx, bit)
    data = enc.flush()

    dec = ArithmeticDecoder(ImageInputStream(data))
    dec_cx = CX(8, 0)
    out = []
    for idx in indices:
        dec_cx.set_index(idx)
        out.append(dec.decode(dec_cx))
    assert out == bits


def _iax_roundtrip(values: list[int]) -> list[int]:
    enc = MQEncoder()
    int_enc = ArithmeticIntegerEncoder(enc)
    enc_cx = Cx(512, 1)
    for v in values:
        int_enc.encode(enc_cx, v)
    data = enc.flush()

    dec = ArithmeticDecoder(ImageInputStream(data))
    int_dec = ArithmeticIntegerDecoder(dec)
    dec_cx = CX(512, 1)
    out = []
    for _ in values:
        d = int_dec.decode(dec_cx)
        out.append(OOB if d == LONG_MAX_VALUE else d)
    return out


@pytest.mark.parametrize(
    "values",
    [
        [0],
        [1, 2, 3],
        [-1, -2, -3],
        [0, 3, 4, 19, 20, 83, 84, 339, 340, 4435, 4436],
        [-4436, -340, -84, -20, -4, 4436],
        [OOB],
        [5, OOB, 7, -7, OOB, 0],
        list(range(-50, 200)),
    ],
)
def test_iax_integer_roundtrip(values):
    assert _iax_roundtrip(values) == values


def test_iaid_roundtrip():
    sym_code_len = 5
    ids = [0, 1, 2, 7, 15, 31, 3, 0, 31]
    enc = MQEncoder()
    int_enc = ArithmeticIntegerEncoder(enc)
    enc_cx = Cx(1 << sym_code_len, 1)
    for sid in ids:
        int_enc.encode_iaid(enc_cx, sid, sym_code_len)
    data = enc.flush()

    dec = ArithmeticDecoder(ImageInputStream(data))
    int_dec = ArithmeticIntegerDecoder(dec)
    dec_cx = CX(1 << sym_code_len, 1)
    out = [int_dec.decode_iaid(dec_cx, sym_code_len) for _ in ids]
    assert out == ids
