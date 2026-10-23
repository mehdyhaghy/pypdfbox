"""Differential fuzz: ASCII85 stdlib fast paths vs the exact per-byte port.

``ASCII85Decode._decode_bytes`` uses ``base64.a85decode`` (when it is C
accelerated) and ``ASCII85OutputStream.write`` bulk-encodes whole groups
with ``base64.a85encode``. Both must stay byte-identical to the upstream
``ASCII85InputStream`` / ``ASCII85OutputStream`` algorithms. The references
here are self-contained per-byte transcriptions of those algorithms, so the
fuzz compares the shipped code against them on random data, random chunked
writes, odd line lengths, and random or malformed ASCII85 input.
"""

import io
import random

import pytest

from pypdfbox.cos import COSDictionary
from pypdfbox.filter import ASCII85Decode
from pypdfbox.filter.ascii85_output_stream import ASCII85OutputStream


def _reference_decode(data: bytes) -> bytes:
    # Upstream ASCII85InputStream: stop at the first b'~', skip LF/CR/SPACE,
    # b'z' only at a group boundary, digits b'!'..b'}' with a 32-bit wrap,
    # trailing partial group of n digits padded with b'u' -> n - 1 bytes.
    out = bytearray()
    group: list[int] = []
    for byte in data:
        if byte == 0x7E:
            break
        if byte in (0x0A, 0x0D, 0x20):
            continue
        if byte == 0x7A and not group:
            out += b"\x00\x00\x00\x00"
            continue
        if not 0 <= byte - 0x21 <= 93:
            raise OSError("Invalid data in Ascii85 stream")
        group.append(byte - 0x21)
        if len(group) == 5:
            value = 0
            for d in group:
                value = value * 85 + d
            out += (value & 0xFFFFFFFF).to_bytes(4, "big")
            group = []
    n = len(group)
    if n >= 2:
        value = 0
        for d in group + [84] * (5 - n):
            value = value * 85 + d
        out += (value & 0xFFFFFFFF).to_bytes(4, "big")[: n - 1]
    return bytes(out)


def _reference_encode(data: bytes, line_length: int | None) -> bytes:
    # Upstream ASCII85OutputStream, one byte at a time.
    out = bytearray()
    line_break = max_line = 72
    if line_length is not None:
        if line_break > line_length:
            line_break = line_length
        max_line = line_length

    def emit(chars: bytes) -> None:
        nonlocal line_break
        for c in chars:
            out.append(c)
            line_break -= 1
            if line_break == 0:
                out.append(0x0A)
                line_break = max_line

    def digits(word: int) -> bytes:
        res = bytearray(5)
        for i in range(4, -1, -1):
            res[i] = word % 85 + 0x21
            word //= 85
        return bytes(res)

    if not data:
        return b""
    full = len(data) - len(data) % 4
    for i in range(0, full, 4):
        word = int.from_bytes(data[i : i + 4], "big")
        emit(b"z" if word == 0 else digits(word))
    rest = len(data) - full
    if rest:
        word = int.from_bytes(data[full:] + b"\x00" * (4 - rest), "big")
        emit(digits(word)[: rest + 1])
    line_break -= 1
    if line_break == 0:
        out.append(0x0A)
    out += b"~>\n"
    return bytes(out)


def _decode(data: bytes) -> bytes | tuple[str, str]:
    out = io.BytesIO()
    try:
        ASCII85Decode().decode(io.BytesIO(data), out, COSDictionary(), 0)
    except OSError as exc:
        return ("error", str(exc))
    return out.getvalue()


def _ref_decode(data: bytes) -> bytes | tuple[str, str]:
    try:
        return _reference_decode(data)
    except OSError as exc:
        return ("error", str(exc))


def _encode(
    data: bytes, line_length: int | None, rng: random.Random | None
) -> bytes:
    sink = io.BytesIO()
    stream = ASCII85OutputStream(sink)
    if line_length is not None:
        stream.set_line_length(line_length)
    if rng is None:
        stream.write(data)
    else:
        pos = 0
        while pos < len(data):
            step = rng.randint(0, 9)
            stream.write(data[pos : pos + step])
            pos += step
    stream.flush()
    return sink.getvalue()


def _random_payload(rng: random.Random) -> bytes:
    size = rng.choice([0, 1, 2, 3, 4, 5, 7, 8, 16, 57, 71, 72, 100, 288])
    kind = rng.random()
    if kind < 0.4:
        return bytes(rng.getrandbits(8) for _ in range(size))
    if kind < 0.7:
        return bytes(rng.choice(b"\x00\x00\x00\x01\xff") for _ in range(size))
    return bytes(rng.choice(b"\x00\xff") for _ in range(size))


_ALPHABET = bytes(range(0x21, 0x7F)) + b" \n\r\t\x00\x0c\x7fzzzzuuuu~~"


@pytest.mark.parametrize("seed", range(4))
def test_encode_matches_reference(seed: int) -> None:
    rng = random.Random(seed)
    for _ in range(1500):
        data = _random_payload(rng)
        line_length = rng.choice([None, None, 72, 1, 2, 5, 71, 0, -3])
        chunked = rng.random() < 0.3
        expected = _reference_encode(data, line_length)
        got = _encode(data, line_length, random.Random(seed) if chunked else None)
        assert got == expected, (data, line_length, chunked)


def test_encode_filter_matches_reference() -> None:
    rng = random.Random(99)
    for _ in range(300):
        data = _random_payload(rng)
        sink = io.BytesIO()
        ASCII85Decode().encode(io.BytesIO(data), sink, COSDictionary())
        assert sink.getvalue() == _reference_encode(data, None)


@pytest.mark.parametrize("seed", range(4))
def test_decode_matches_reference(seed: int) -> None:
    rng = random.Random(1000 + seed)
    for _ in range(800):
        encoded = _reference_encode(_random_payload(rng), None)
        variants = [encoded, encoded.replace(b"~>", b""), encoded + b"junk~>more"]
        for _ in range(3):
            mutated = bytearray(encoded)
            for _ in range(rng.randint(1, 4)):
                op = rng.random()
                if op < 0.4 and mutated:
                    mutated[rng.randrange(len(mutated))] = rng.choice(_ALPHABET)
                elif op < 0.7:
                    mutated.insert(rng.randint(0, len(mutated)), rng.choice(_ALPHABET))
                elif mutated:
                    del mutated[rng.randrange(len(mutated))]
            variants.append(bytes(mutated))
        variants.append(bytes(rng.choice(_ALPHABET) for _ in range(rng.randint(0, 40))))
        variants.append(bytes(rng.choice(b"!uz") for _ in range(rng.randint(0, 40))))
        for data in variants:
            assert _decode(data) == _ref_decode(data), data


@pytest.mark.parametrize(
    "data",
    [
        b"!",  # lone digit: dropped (3.15 stdlib raises)
        b"!!!!!z!",  # z at boundary then lone digit
        b"!z!!!",  # mid-group z is an ordinary digit
        b"uu",  # padded partial group overflows: wraps
        b's8W-"',  # full-group overflow: wraps
        b"vwxy}",  # digits above b'u' are accepted upstream
        b"87cURD\t]i,\"Ebo80~>",  # TAB is not whitespace upstream
        b"87cURD~X",  # first b'~' ends the stream
        b"",
        b"~>",
        b" \r\n",
    ],
    ids=[
        "lone_digit",
        "z_then_lone",
        "mid_group_z",
        "partial_overflow",
        "full_overflow",
        "high_digits",
        "tab_invalid",
        "tilde_only_eod",
        "empty",
        "eod_only",
        "whitespace_only",
    ],
)
def test_decode_edge_cases(data: bytes) -> None:
    assert _decode(data) == _ref_decode(data)
