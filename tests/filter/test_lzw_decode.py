from __future__ import annotations

import os
import random
from io import BytesIO

import pytest

from pypdfbox.cos import COSDictionary, COSInteger, COSName
from pypdfbox.filter import FilterFactory, LZWDecode
from pypdfbox.filter.lzw_decode import (
    CLEAR_TABLE,
    EOD,
    _BitReader,
    _BitWriter,
    _calculate_chunk,
)

# ---------- helpers ---------------------------------------------------


def _roundtrip(data: bytes, params: COSDictionary | None = None) -> bytes:
    """Encode then decode ``data`` through LZWDecode and return the
    decoded bytes. Asserts the round-trip is lossless along the way."""
    f = LZWDecode()
    enc = BytesIO()
    f.encode(BytesIO(data), enc, params)
    dec = BytesIO()
    f.decode(BytesIO(enc.getvalue()), dec, params)
    return dec.getvalue()


def _decode(encoded: bytes, params: COSDictionary | None = None) -> bytes:
    f = LZWDecode()
    out = BytesIO()
    f.decode(BytesIO(encoded), out, params)
    return out.getvalue()


class _FlushTrackingBytesIO(BytesIO):
    def __init__(self) -> None:
        super().__init__()
        self.flush_count = 0

    def flush(self) -> None:
        self.flush_count += 1
        super().flush()


def _make_params(
    early_change: int | None = None,
    predictor: int | None = None,
    columns: int | None = None,
    colors: int | None = None,
    bits_per_component: int | None = None,
) -> COSDictionary:
    """Build a ``/DecodeParms``-style dictionary."""
    inner = COSDictionary()
    if early_change is not None:
        inner.set_int("EarlyChange", early_change)
    if predictor is not None:
        inner.set_int("Predictor", predictor)
    if columns is not None:
        inner.set_int("Columns", columns)
    if colors is not None:
        inner.set_int("Colors", colors)
    if bits_per_component is not None:
        inner.set_int("BitsPerComponent", bits_per_component)
    outer = COSDictionary()
    outer.set_item("DecodeParms", inner)
    return outer


# ---------- bit reader / writer ---------------------------------------


def test_bit_reader_msb_first() -> None:
    # 0xAB 0xCD = 1010 1011 1100 1101
    src = BytesIO(bytes([0xAB, 0xCD]))
    r = _BitReader(src)
    assert r.read_bits(4) == 0xA
    assert r.read_bits(4) == 0xB
    assert r.read_bits(8) == 0xCD


def test_bit_reader_eof_raises() -> None:
    r = _BitReader(BytesIO(b""))
    with pytest.raises(EOFError):
        r.read_bits(9)


def test_bit_writer_round_trip() -> None:
    dst = BytesIO()
    w = _BitWriter(dst)
    w.write_bits(0xA, 4)
    w.write_bits(0xB, 4)
    w.write_bits(0xCD, 8)
    w.flush()
    assert dst.getvalue() == bytes([0xAB, 0xCD])


def test_bit_writer_pads_with_zeros() -> None:
    dst = BytesIO()
    w = _BitWriter(dst)
    w.write_bits(0b101, 3)
    w.flush()
    # 101 -> high three bits, padded with zeros -> 1010 0000 = 0xA0
    assert dst.getvalue() == bytes([0xA0])


# ---------- chunk-size calculation -----------------------------------


def test_calculate_chunk_early_change_default() -> None:
    # EarlyChange=1: width grows when next code would be 511/1023/2047.
    assert _calculate_chunk(0, True) == 9
    assert _calculate_chunk(510, True) == 9
    assert _calculate_chunk(511, True) == 10
    assert _calculate_chunk(1022, True) == 10
    assert _calculate_chunk(1023, True) == 11
    assert _calculate_chunk(2046, True) == 11
    assert _calculate_chunk(2047, True) == 12


def test_calculate_chunk_no_early_change() -> None:
    assert _calculate_chunk(511, False) == 9
    assert _calculate_chunk(512, False) == 10
    assert _calculate_chunk(1023, False) == 10
    assert _calculate_chunk(1024, False) == 11
    assert _calculate_chunk(2047, False) == 11
    assert _calculate_chunk(2048, False) == 12


# ---------- end-to-end round-trips ------------------------------------


def test_round_trip_canonical_lzw_sample() -> None:
    # Classic textbook LZW worked example.
    data = b"TOBEORNOTTOBEORTOBEORNOT#"
    assert _roundtrip(data) == data


def test_round_trip_empty() -> None:
    assert _roundtrip(b"") == b""


def test_empty_input_emits_clear_then_eod() -> None:
    # Encode of empty input must be just CLEAR (256) + EOD (257), both
    # at 9 bits = 18 bits total = 3 bytes (zero-padded).
    f = LZWDecode()
    enc = BytesIO()
    f.encode(BytesIO(b""), enc, None)
    encoded = enc.getvalue()
    # Re-decode to confirm.
    assert _decode(encoded) == b""
    # Sanity-read the first two codes ourselves.
    r = _BitReader(BytesIO(encoded))
    assert r.read_bits(9) == CLEAR_TABLE
    assert r.read_bits(9) == EOD


def test_round_trip_single_byte() -> None:
    assert _roundtrip(b"A") == b"A"


def test_round_trip_two_bytes() -> None:
    assert _roundtrip(b"AB") == b"AB"


def test_round_trip_repeated_byte_kwkwk_case() -> None:
    # Highly repetitive input forces the KwKwK special case in the
    # decoder where a code points at the entry being created.
    data = b"A" * 1024
    assert _roundtrip(data) == data


def test_round_trip_grows_past_9_bits() -> None:
    # A long alphabetic run accumulates well over 256 new entries,
    # forcing the code width to grow through 10 and 11 bits.
    rng = random.Random(0xCAFEBABE)
    data = bytes(rng.randrange(256) for _ in range(8000))
    assert _roundtrip(data) == data


def test_round_trip_grows_past_11_bits() -> None:
    # Even longer run to push past the 11->12 boundary.
    rng = random.Random(0xDEADBEEF)
    data = bytes(rng.randrange(256) for _ in range(20000))
    assert _roundtrip(data) == data


def test_round_trip_full_table_clear() -> None:
    # 60_000 bytes guarantees the encoder hits the 4096-entry cap and
    # emits an explicit mid-stream CLEAR_TABLE.
    rng = random.Random(0xFEEDFACE)
    data = bytes(rng.randrange(256) for _ in range(60000))
    assert _roundtrip(data) == data


def test_round_trip_all_byte_values() -> None:
    data = bytes(range(256)) * 4
    assert _roundtrip(data) == data


# ---------- explicit handcrafted streams ------------------------------


def _build_stream(codes: list[tuple[int, int]]) -> bytes:
    """Pack ``(code, width)`` pairs into a byte string MSB-first."""
    dst = BytesIO()
    w = _BitWriter(dst)
    for code, width in codes:
        w.write_bits(code, width)
    w.flush()
    return dst.getvalue()


def test_handcrafted_clear_resets_table_mid_stream() -> None:
    # CLEAR, 'A', 'B', CLEAR, 'X', 'Y', EOD — all at 9 bits since the
    # table never grows enough to widen.
    stream = _build_stream(
        [
            (CLEAR_TABLE, 9),
            (ord("A"), 9),
            (ord("B"), 9),
            (CLEAR_TABLE, 9),
            (ord("X"), 9),
            (ord("Y"), 9),
            (EOD, 9),
        ]
    )
    assert _decode(stream) == b"ABXY"


def test_handcrafted_just_eod() -> None:
    stream = _build_stream([(EOD, 9)])
    assert _decode(stream) == b""


def test_handcrafted_clear_then_eod() -> None:
    stream = _build_stream([(CLEAR_TABLE, 9), (EOD, 9)])
    assert _decode(stream) == b""


# ---------- EarlyChange parameter ------------------------------------


def test_early_change_default_explicit_param() -> None:
    data = b"TOBEORNOTTOBEORTOBEORNOT#" * 100
    params = _make_params(early_change=1)
    assert _roundtrip(data, params) == data


def test_decode_with_early_change_zero_handcrafted() -> None:
    # Build an EarlyChange=0 stream by hand: emit 'A' through 'P' (15
    # entries beyond 257 -> table size 273) and the chunk stays at 9
    # for the entire short run. Then verify decode honors EarlyChange=0
    # by computing chunk widths the slow way.
    text = b"HELLO LZW WORLD"
    f = LZWDecode()
    # Build expected codes by simulating the encoder with EarlyChange=0.
    # For short inputs, all codes are 9 bits with either flag, so this
    # really just exercises the decode path with the parameter.
    enc = BytesIO()
    f.encode(BytesIO(text), enc, _make_params(early_change=1))
    # The current encoder always emits EarlyChange=1 streams; for a
    # short input the bytes happen to be valid under both interpretations
    # only if no width-change point is crossed. Verify by decoding with
    # EarlyChange=0 against an input small enough not to cross 9 bits.
    short = b"AB"
    enc2 = BytesIO()
    f.encode(BytesIO(short), enc2, _make_params(early_change=1))
    out = BytesIO()
    # Decoding with EarlyChange=0 should still produce the right answer
    # because the table never approaches width-change boundaries here.
    f.decode(BytesIO(enc2.getvalue()), out, _make_params(early_change=0))
    assert out.getvalue() == short


def test_decode_handcrafted_early_change_zero_stream() -> None:
    # Hand-built stream that grows the table enough to hit a width
    # change with EarlyChange=0 semantics. We construct a short program
    # the decoder must interpret correctly.
    #
    # Plan: CLEAR, then emit single-byte codes 0..255 in order, which
    # creates table entries 258..513 (each new code = prev + first(curr)
    # so we get 2-byte entries). After the byte that makes the table
    # size 512, EarlyChange=0 says next code is still 9 bits; the 513th
    # entry flips us to 10 bits. We just verify decode runs without
    # crashing and produces correct output.
    codes: list[tuple[int, int]] = [(CLEAR_TABLE, 9)]
    table_size = 258
    prev_set = False
    for i in range(300):
        # Width is computed against the current table_size: the decoder
        # reads the code at the current chunk, then appends a new entry
        # (only if this isn't the first code after CLEAR, since there
        # is no prev to seed the new entry from), then recomputes chunk.
        chunk = _calculate_chunk(table_size, early_change=False)
        codes.append((i % 256, chunk))
        if prev_set:
            table_size += 1
        prev_set = True
    codes.append((EOD, _calculate_chunk(table_size, early_change=False)))
    stream = _build_stream(codes)
    out = _decode(stream, _make_params(early_change=0))
    expected = bytes(i % 256 for i in range(300))
    assert out == expected


# ---------- predictor support ----------------------------------------


def _png_up_encode(data: bytes, columns: int) -> bytes:
    """Encode raw image data with PNG predictor #2 ('Up') prepended
    per-row. Used to construct LZW streams whose decoded output is
    valid PNG predictor data, then run the LZW filter with /Predictor 12.
    """
    rows = [data[i : i + columns] for i in range(0, len(data), columns)]
    out = bytearray()
    prev = bytes(columns)
    for row in rows:
        if len(row) < columns:
            row = row + bytes(columns - len(row))
        out.append(2)  # filter byte: 2 = Up
        out.extend((b - p) & 0xFF for b, p in zip(row, prev, strict=False))
        prev = row
    return bytes(out)


def test_predictor_png_up() -> None:
    # 4 columns x 3 rows of arbitrary data.
    raw = bytes([10, 20, 30, 40, 11, 22, 33, 44, 50, 60, 70, 80])
    columns = 4
    pre_encoded = _png_up_encode(raw, columns)

    # Encode the predictor-encoded bytes through LZW (no params for
    # encode — predictor is a decode-side post-step).
    f = LZWDecode()
    enc = BytesIO()
    f.encode(BytesIO(pre_encoded), enc, None)

    # Decode with /Predictor 12 /Columns 4 -> we should recover the
    # original raw image bytes.
    params = _make_params(predictor=12, columns=columns, colors=1, bits_per_component=8)
    dec = BytesIO()
    f.decode(BytesIO(enc.getvalue()), dec, params)
    assert dec.getvalue() == raw


def test_predictor_tiff_sub_8bit() -> None:
    # Predictor 2 (TIFF SUB), 8 bits per component, 1 color, 4 columns.
    columns = 4
    raw = bytes([10, 30, 60, 100, 5, 10, 15, 20, 200, 210, 220, 230])
    rows = [raw[i : i + columns] for i in range(0, len(raw), columns)]
    sub_encoded = bytearray()
    for row in rows:
        sub_encoded.append(row[0])
        for i in range(1, len(row)):
            sub_encoded.append((row[i] - row[i - 1]) & 0xFF)

    f = LZWDecode()
    enc = BytesIO()
    f.encode(BytesIO(bytes(sub_encoded)), enc, None)
    params = _make_params(predictor=2, columns=columns, colors=1, bits_per_component=8)
    dec = BytesIO()
    f.decode(BytesIO(enc.getvalue()), dec, params)
    assert dec.getvalue() == raw


def test_predictor_one_is_passthrough() -> None:
    data = b"hello world" * 10
    params = _make_params(predictor=1)
    assert _roundtrip(data, params) == data


# ---------- error handling -------------------------------------------


def test_truncated_stream_without_eod_stops_without_error() -> None:
    # A single byte cannot encode a full 9-bit code plus EOD.
    f = LZWDecode()
    out = BytesIO()
    f.decode(BytesIO(b"\x00"), out, None)
    assert out.getvalue() == b""


def test_truncated_after_clear_without_eod_stops_without_error() -> None:
    # CLEAR followed by half a code, no EOD.
    half_code = _build_stream([(CLEAR_TABLE, 9)])
    # Drop the trailing byte to truncate the next 9-bit slot mid-byte.
    truncated = half_code[:1]
    f = LZWDecode()
    out = BytesIO()
    f.decode(BytesIO(truncated), out, None)
    assert out.getvalue() == b""


def test_missing_eod_after_valid_data_returns_decoded_prefix() -> None:
    stream = _build_stream([(CLEAR_TABLE, 9), (ord("A"), 9), (ord("B"), 9)])

    assert _decode(stream) == b"AB"


def test_invalid_code_raises_oserror() -> None:
    # Reference a code well beyond the initial table without ever
    # populating it. CLEAR, then code 500 (way past 258), then EOD.
    stream = _build_stream([(CLEAR_TABLE, 9), (500, 9), (EOD, 9)])
    f = LZWDecode()
    out = BytesIO()
    with pytest.raises(OSError):
        f.decode(BytesIO(stream), out, None)


def test_reserved_code_referenced_as_data_raises() -> None:
    # CLEAR, then 'A', then explicitly use code 256 as data (not as the
    # CLEAR sentinel — wait, the decoder always treats 256 as CLEAR).
    # Use code 257 (EOD) inline followed by another EOD: the decoder
    # will stop at the first EOD. So instead force a placeholder hit
    # by a contrived second-CLEAR-without-prev pattern. Simpler: build
    # a stream that resolves to None via direct corruption.
    #
    # Build CLEAR, code 257-1 = 256 -> CLEAR resets again; that's
    # legal. The genuinely-invalid case is "code = current table size
    # without a prev" — which the decoder rejects.
    stream = _build_stream([(CLEAR_TABLE, 9), (258, 9), (EOD, 9)])
    f = LZWDecode()
    out = BytesIO()
    with pytest.raises(OSError):
        f.decode(BytesIO(stream), out, None)


# ---------- registration ---------------------------------------------


def test_filter_factory_get_long_name() -> None:
    inst = FilterFactory.get("LZWDecode")
    assert isinstance(inst, LZWDecode)


def test_filter_factory_get_abbreviation() -> None:
    inst = FilterFactory.get("LZW")
    assert isinstance(inst, LZWDecode)


def test_filter_factory_get_cosname() -> None:
    inst = FilterFactory.get(COSName.get_pdf_name("LZWDecode"))
    assert isinstance(inst, LZWDecode)


def test_filter_factory_is_registered() -> None:
    assert FilterFactory.is_registered("LZWDecode")
    assert FilterFactory.is_registered("LZW")


# ---------- decode-result accounting ---------------------------------


def test_decode_result_byte_count() -> None:
    f = LZWDecode()
    enc = BytesIO()
    payload = b"hello LZW" * 50
    f.encode(BytesIO(payload), enc, None)
    out = BytesIO()
    result = f.decode(BytesIO(enc.getvalue()), out, None)
    assert result.bytes_written == len(payload)
    assert out.getvalue() == payload


def test_decode_flushes_decoded_sink_after_write() -> None:
    f = LZWDecode()
    enc = BytesIO()
    payload = b"flush me through lzw"
    f.encode(BytesIO(payload), enc, None)
    out = _FlushTrackingBytesIO()

    result = f.decode(BytesIO(enc.getvalue()), out, None)

    assert out.getvalue() == payload
    assert result.bytes_written == len(payload)
    assert out.flush_count == 1


def test_encode_flushes_encoded_sink_after_final_byte() -> None:
    out = _FlushTrackingBytesIO()

    LZWDecode().encode(BytesIO(b"flush me through lzw"), out, None)

    assert out.getvalue()
    assert out.flush_count == 1


def test_decode_returns_input_parameters_when_provided() -> None:
    f = LZWDecode()
    enc = BytesIO()
    f.encode(BytesIO(b"hi"), enc, None)
    params = COSDictionary()
    params.set_item("Length", COSInteger.get(2))
    result = f.decode(BytesIO(enc.getvalue()), BytesIO(), params)
    assert result.parameters is params


# ---------- corpus sanity ---------------------------------------------


def test_random_round_trip_assorted_sizes() -> None:
    rng = random.Random(0xABCDEF)
    for size in (0, 1, 2, 3, 16, 100, 257, 1000, 5000):
        data = bytes(rng.randrange(256) for _ in range(size))
        assert _roundtrip(data) == data, f"failed for size {size}"


def test_round_trip_text_repeats() -> None:
    data = (b"the quick brown fox jumps over the lazy dog\n" * 200)
    assert _roundtrip(data) == data


def test_round_trip_binary_with_zero_runs() -> None:
    data = b"\x00" * 1000 + b"\xff" * 1000 + os.urandom(1000)
    assert _roundtrip(data) == data
