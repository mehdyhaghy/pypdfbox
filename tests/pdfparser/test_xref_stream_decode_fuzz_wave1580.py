"""Wave 1580: differential fuzz for cross-reference STREAM decoding.

Hammers ``PDFXrefStreamParser`` (``/Type /XRef`` binary decoder) against a
pure-Python reference that mirrors upstream
``org.apache.pdfbox.pdfparser.PDFXrefStreamParser`` line-for-line:

 * ``/W [w0 w1 w2]`` field-width parsing — including a 0-width type field
   (``w0 == 0`` ⇒ type defaults to 1, per PDF spec / Java line 136), and a
   0-width third field (gen / objstm-index defaults to 0 via parseValue).
 * ``/Index [start count ...]`` subsection iteration — single default
   ``[0 Size]``, several subsections, and the ``start + count`` ⇒
   object-number mapping.
 * type-0 (free, skipped), type-1 (offset, gen), type-2 (objstm number,
   index-within) entries and the negative-offset sign convention for type-2.
 * big-endian multi-byte field assembly.
 * ``/Index`` count vs. actual body-length mismatch (EOF stops the loop).
 * entries declared beyond ``/Size``.
 * FlateDecode body (with and without a PNG predictor) — the parser reads
   through ``COSStream.create_view`` which decodes the filter chain.

The reference (`_reference_decode`) is independent of the production code so
a divergence in either surfaces as a test failure.
"""

from __future__ import annotations

import random
import struct
import zlib

import pytest

from pypdfbox.cos.cos_array import COSArray
from pypdfbox.cos.cos_dictionary import COSDictionary
from pypdfbox.cos.cos_document import COSDocument
from pypdfbox.cos.cos_integer import COSInteger
from pypdfbox.cos.cos_name import COSName
from pypdfbox.cos.cos_stream import COSStream
from pypdfbox.pdfparser.parse_error import PDFParseError
from pypdfbox.pdfparser.pdf_xref_stream_parser import PDFXrefStreamParser
from pypdfbox.pdfparser.xref_trailer_resolver import XrefTrailerResolver

# ---------------------------------------------------------------------------
# Synthetic xref-stream builders
# ---------------------------------------------------------------------------


def _encode_entry(w: list[int], type_: int, f2: int, f3: int) -> bytes:
    """Encode one (type, field2, field3) row big-endian into w[i] bytes each.

    A 0-width field contributes no bytes (the spec's default-value mechanism).
    """
    out = bytearray()
    for width, value in zip(w, (type_, f2, f3), strict=True):
        if width == 0:
            continue
        out += value.to_bytes(width, "big")
    return bytes(out)


def _encode_body(w: list[int], rows: list[tuple[int, int, int]]) -> bytes:
    body = bytearray()
    for type_, f2, f3 in rows:
        body += _encode_entry(w, type_, f2, f3)
    return bytes(body)


def _make_stream(
    w: list[int] | None,
    index: list[int] | None,
    body: bytes,
    *,
    size: int | None = None,
    flate: bool = False,
    predictor: int | None = None,
    columns: int | None = None,
) -> COSStream:
    stream = COSStream()
    if w is not None:
        w_arr = COSArray()
        for v in w:
            w_arr.add(COSInteger.get(v))
        stream.set_item(COSName.W, w_arr)
    if index is not None:
        idx_arr = COSArray()
        for v in index:
            idx_arr.add(COSInteger.get(v))
        stream.set_item(COSName.INDEX, idx_arr)
    if size is not None:
        stream.set_item(COSName.SIZE, COSInteger.get(size))

    if flate:
        # Optionally apply a PNG predictor by hand, then deflate. We write the
        # already-deflated bytes raw and declare the filter so create_view
        # inflates (and un-predicts) on read.
        payload = body
        if predictor is not None and predictor >= 10:
            assert columns is not None
            payload = _apply_png_up_predictor(body, columns)
            decode_parms = COSDictionary()
            decode_parms.set_item(
                COSName.get_pdf_name("Predictor"), COSInteger.get(predictor)
            )
            decode_parms.set_item(
                COSName.get_pdf_name("Columns"), COSInteger.get(columns)
            )
            stream.set_item(COSName.get_pdf_name("DecodeParms"), decode_parms)
        deflated = zlib.compress(payload)
        stream.set_item(COSName.FILTER, COSName.FLATE_DECODE)
        out = stream.create_raw_output_stream()
        try:
            out.write(deflated)
        finally:
            out.close()
    else:
        out = stream.create_raw_output_stream()
        try:
            out.write(body)
        finally:
            out.close()
    return stream


def _apply_png_up_predictor(body: bytes, columns: int) -> bytes:
    """Prepend a PNG "Up" (filter-type 2) tag to each row and store row-up
    deltas so the standard FlateDecode predictor inverse recovers ``body``."""
    assert len(body) % columns == 0
    out = bytearray()
    prev = bytes(columns)
    for off in range(0, len(body), columns):
        row = body[off : off + columns]
        out.append(2)  # PNG filter type "Up"
        out += bytes((row[i] - prev[i]) & 0xFF for i in range(columns))
        prev = row
    return bytes(out)


# ---------------------------------------------------------------------------
# Independent reference decoder — mirrors PDFXrefStreamParser.parse
# ---------------------------------------------------------------------------


def _ref_parse_value(data: bytes, start: int, length: int) -> int:
    value = 0
    for i in range(length):
        value += (data[i + start] & 0xFF) << ((length - i - 1) * 8)
    return value


def _ref_object_numbers(index: list[int], limit: int) -> list[int]:
    """Mirror ``PDFXrefStreamParser.ObjectNumbers`` exactly — including its
    quirk for an empty (count == 0) subsection: when a range boundary is
    crossed the iterator unconditionally emits the *next* range's start
    before re-checking emptiness, so a ``[start 0]`` subsection still yields
    one object number (``start``). We bound the walk by ``limit`` (the number
    of decodable rows) to mirror the ``isEOF()`` loop guard.
    """
    starts = [index[i] for i in range(0, len(index), 2)]
    ends = [index[i] + index[i + 1] for i in range(0, len(index), 2)]
    nums: list[int] = []
    current_range = 0
    current_number = starts[0]
    current_end = ends[0]

    def _has_next() -> bool:
        if len(starts) == 1:
            return current_number < current_end
        return current_range < len(starts) - 1 or current_number < current_end

    while _has_next() and len(nums) < limit:
        if current_number < current_end:
            nums.append(current_number)
            current_number += 1
            continue
        if current_range >= len(starts) - 1:
            break
        current_range += 1
        current_number = starts[current_range]
        current_end = ends[current_range]
        nums.append(current_number)
        current_number += 1
    return nums


def _reference_decode(
    w: list[int], index: list[int], decoded_body: bytes
) -> list[tuple[int, int, int, int]]:
    """Return (obj_num, type, field2, field3) for the in-use rows the upstream
    algorithm would feed to the resolver (free entries omitted)."""
    row_len = w[0] + w[1] + w[2]
    # The parser stops as soon as isEOF() is true at the top of the loop, so
    # at most ceil(len/row_len) object numbers are consumed (a 0-length body
    # yields none). Bound the object-number walk accordingly.
    max_rows = 0 if row_len == 0 else (len(decoded_body) + row_len - 1) // row_len
    obj_nums = _ref_object_numbers(index, max_rows)
    out: list[tuple[int, int, int, int]] = []
    pos = 0
    for obj_num in obj_nums:
        if pos >= len(decoded_body):
            break  # EOF — loop guard isEOF()
        row = decoded_body[pos : pos + row_len]
        # readNextValue zero-pads a short final row.
        if len(row) < row_len:
            row = row + bytes(row_len - len(row))
        pos += row_len
        type_ = 1 if w[0] == 0 else _ref_parse_value(row, 0, w[0])
        if type_ == 0:
            continue
        f2 = _ref_parse_value(row, w[0], w[1])
        f3 = _ref_parse_value(row, w[0] + w[1], w[2])
        out.append((obj_num, type_, f2, f3))
    return out


def _run_parser(stream: COSStream) -> dict[int, int]:
    parser = PDFXrefStreamParser(stream, COSDocument())
    resolver = XrefTrailerResolver()
    resolver.begin_section(0)
    parser.parse(resolver)
    table = resolver.get_xref_table()
    return {k.get_number(): v.offset for k, v in table.items()}


def _expected_offsets(rows: list[tuple[int, int, int, int]]) -> dict[int, int]:
    """Translate reference rows to the resolver's stored offset value."""
    out: dict[int, int] = {}
    for obj_num, type_, f2, _f3 in rows:
        out[obj_num] = f2 if type_ == 1 else -f2
    return out


# ---------------------------------------------------------------------------
# 1. /W field-width parsing
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "w",
    [
        [1, 2, 1],
        [1, 3, 0],  # w2 == 0 ⇒ gen / index field defaults to 0
        [1, 4, 2],
        [2, 2, 2],
        [1, 1, 1],
        [0, 2, 1],  # w0 == 0 ⇒ type defaults to 1
        [0, 4, 0],  # only the offset column present
    ],
    ids=["121", "130", "142", "222", "111", "021", "040"],
)
def test_w_widths_roundtrip(w: list[int]) -> None:
    rows = [(1, 0x10, 0x00), (1, 0x2345, 0x01), (1, 0xABCDEF & ((1 << (8 * w[1])) - 1), 0x00)]
    # Clamp generated field-2 values to the encodable width.
    rows = [(t, f2 & ((1 << (8 * w[1])) - 1 if w[1] else 0), f3) for t, f2, f3 in rows]
    body = _encode_body(w, rows)
    index = [1, len(rows)]
    stream = _make_stream(w, index, body)
    got = _run_parser(stream)
    expected = _expected_offsets(_reference_decode(w, index, body))
    assert got == expected


def test_w0_zero_type_defaults_to_one() -> None:
    # No type column at all — every row must be treated as in-use (type 1),
    # never free, never compressed.
    w = [0, 2, 1]
    rows = [(1, 0x00, 0x00), (1, 0xFFFF, 0x00), (1, 0x1234, 0x09)]
    body = _encode_body(w, rows)
    index = [5, 3]
    got = _run_parser(_make_stream(w, index, body))
    assert got == {5: 0x00, 6: 0xFFFF, 7: 0x1234}


def test_w2_zero_third_field_defaults_to_zero() -> None:
    # w2 == 0: type-1 rows store gen 0; the parser must not read into the
    # next row.
    w = [1, 2, 0]
    rows = [(1, 0x1111, 0), (1, 0x2222, 0)]
    body = _encode_body(w, rows)
    index = [0, 2]
    got = _run_parser(_make_stream(w, index, body))
    assert got == {0: 0x1111, 1: 0x2222}


# ---------------------------------------------------------------------------
# 2. /Index subsection iteration
# ---------------------------------------------------------------------------


def test_default_index_uses_zero_size() -> None:
    # Missing /Index ⇒ default [0 Size]. With Size 3 the parser walks objs
    # 0,1,2.
    w = [1, 2, 1]
    rows = [(1, 0x10, 0), (1, 0x20, 0), (1, 0x30, 0)]
    body = _encode_body(w, rows)
    stream = _make_stream(w, None, body, size=3)
    got = _run_parser(stream)
    assert got == {0: 0x10, 1: 0x20, 2: 0x30}


def test_multiple_subsections_object_mapping() -> None:
    # /Index [10 2 100 3] ⇒ objects 10,11,100,101,102 in body order.
    w = [1, 2, 1]
    rows = [
        (1, 0xA0, 0),
        (1, 0xA1, 0),
        (1, 0xC0, 0),
        (1, 0xC1, 0),
        (1, 0xC2, 0),
    ]
    body = _encode_body(w, rows)
    index = [10, 2, 100, 3]
    got = _run_parser(_make_stream(w, index, body))
    assert got == {10: 0xA0, 11: 0xA1, 100: 0xC0, 101: 0xC1, 102: 0xC2}


def test_subsection_with_nonzero_start_offset_objects() -> None:
    w = [1, 2, 1]
    rows = [(1, 0x55, 0), (1, 0x66, 0)]
    body = _encode_body(w, rows)
    index = [42, 2]
    got = _run_parser(_make_stream(w, index, body))
    assert got == {42: 0x55, 43: 0x66}


def test_empty_subsection_still_consumes_one_object_number() -> None:
    # Parity quirk: a [start 0] subsection between two non-empty ones is NOT
    # skipped — upstream ObjectNumbers.next() unconditionally emits the next
    # range's start after a boundary, so object number 409 is consumed and
    # one body row is spent on it. /Index [202 1 409 0 113 2].
    w = [1, 2, 1]
    rows = [(1, 0xAA, 0), (1, 0xBB, 0), (1, 0xCC, 0)]
    body = _encode_body(w, rows)
    index = [202, 1, 409, 0, 113, 2]
    got = _run_parser(_make_stream(w, index, body))
    expected = _expected_offsets(_reference_decode(w, index, body))
    # 202←row0, 409←row1 (the empty range's start), 113←row2.
    assert got == {202: 0xAA, 409: 0xBB, 113: 0xCC}
    assert got == expected


def test_three_subsections() -> None:
    w = [1, 2, 1]
    rows = [(1, n, 0) for n in (1, 2, 3, 4, 5)]
    body = _encode_body(w, rows)
    index = [0, 1, 5, 2, 20, 2]
    got = _run_parser(_make_stream(w, index, body))
    expected = _expected_offsets(_reference_decode(w, index, body))
    assert got == {0: 1, 5: 2, 6: 3, 20: 4, 21: 5}
    assert got == expected


# ---------------------------------------------------------------------------
# 3. Entry types 0 / 1 / 2
# ---------------------------------------------------------------------------


def test_type0_free_entries_skipped() -> None:
    w = [1, 2, 1]
    rows = [(0, 0x00, 0xFF), (1, 0x42, 0), (0, 0, 0), (1, 0x99, 0)]
    body = _encode_body(w, rows)
    index = [3, 4]
    got = _run_parser(_make_stream(w, index, body))
    assert got == {4: 0x42, 6: 0x99}


def test_type1_offset_and_generation() -> None:
    w = [1, 3, 2]
    rows = [(1, 0x010203, 7), (1, 0x040506, 0)]
    body = _encode_body(w, rows)
    index = [0, 2]
    parser = PDFXrefStreamParser(_make_stream(w, index, body), COSDocument())
    resolver = XrefTrailerResolver()
    resolver.begin_section(0)
    parser.parse(resolver)
    table = resolver.get_xref_table()
    by_num = {k.get_number(): k for k in table}
    # Type-1: third field is the generation number on the key.
    assert by_num[0].get_generation() == 7
    assert by_num[1].get_generation() == 0
    assert table[by_num[0]].offset == 0x010203


def test_type2_objstm_number_and_index_not_swapped() -> None:
    # Field2 = parent object-stream number, field3 = index inside it.
    # Stored offset is -field2; the key's generation is 0 (compressed).
    w = [1, 2, 1]
    rows = [(2, 9, 3)]  # objstm 9, index 3
    body = _encode_body(w, rows)
    index = [12, 1]
    parser = PDFXrefStreamParser(_make_stream(w, index, body), COSDocument())
    resolver = XrefTrailerResolver()
    resolver.begin_section(0)
    parser.parse(resolver)
    table = resolver.get_xref_table()
    key = next(iter(table))
    assert key.get_number() == 12
    assert key.get_generation() == 0
    # -objstm number, NOT -index ⇒ guards against a field2/field3 swap.
    assert table[key].offset == -9


def test_mixed_types_in_one_stream() -> None:
    w = [1, 2, 1]
    rows = [
        (0, 0, 0xFF),  # free
        (1, 0x100, 0),  # in-use
        (2, 8, 0),  # compressed, objstm 8 index 0
        (2, 8, 1),  # compressed, objstm 8 index 1
        (1, 0x200, 2),  # in-use gen 2
    ]
    body = _encode_body(w, rows)
    index = [0, 5]
    got = _run_parser(_make_stream(w, index, body))
    expected = _expected_offsets(_reference_decode(w, index, body))
    assert got == expected
    assert got == {1: 0x100, 2: -8, 3: -8, 4: 0x200}


# ---------------------------------------------------------------------------
# 4. Big-endian multi-byte assembly
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("width", "value"),
    [
        (1, 0xAB),
        (2, 0xABCD),
        (3, 0xABCDEF),
        (4, 0x01020304),
        (5, 0x0102030405),
    ],
    ids=["w1", "w2", "w3", "w4", "w5"],
)
def test_big_endian_offset_assembly(width: int, value: int) -> None:
    w = [1, width, 1]
    body = _encode_body(w, [(1, value, 0)])
    got = _run_parser(_make_stream(w, [0, 1], body))
    assert got == {0: value}
    # Confirm the static helper assembles big-endian identically.
    raw = value.to_bytes(width, "big")
    assert PDFXrefStreamParser.parse_value(bytearray(raw), 0, width) == value


# ---------------------------------------------------------------------------
# 5. /Index count vs. body-length mismatch
# ---------------------------------------------------------------------------


def test_index_count_exceeds_body_stops_at_eof() -> None:
    # /Index claims 5 objects, body has 2 ⇒ only 2 parsed.
    w = [1, 2, 1]
    rows = [(1, 0x10, 0), (1, 0x20, 0)]
    body = _encode_body(w, rows)
    index = [0, 5]
    got = _run_parser(_make_stream(w, index, body))
    assert got == {0: 0x10, 1: 0x20}


def test_body_longer_than_index_truncates_to_index() -> None:
    # Body carries 4 rows but /Index only covers 2 ⇒ last 2 ignored.
    w = [1, 2, 1]
    rows = [(1, n, 0) for n in (0x10, 0x20, 0x30, 0x40)]
    body = _encode_body(w, rows)
    index = [0, 2]
    got = _run_parser(_make_stream(w, index, body))
    assert got == {0: 0x10, 1: 0x20}


def test_entries_beyond_size_still_mapped_by_index() -> None:
    # /Size is just metadata for the default-index path; an explicit /Index
    # with object numbers >= Size is honoured verbatim.
    w = [1, 2, 1]
    rows = [(1, 0x77, 0)]
    body = _encode_body(w, rows)
    stream = _make_stream(w, [999, 1], body, size=3)
    got = _run_parser(stream)
    assert got == {999: 0x77}


# ---------------------------------------------------------------------------
# 6. Error paths
# ---------------------------------------------------------------------------


def test_missing_w_raises() -> None:
    body = b""
    stream = _make_stream(None, [0, 1], body)
    with pytest.raises(PDFParseError):
        PDFXrefStreamParser(stream, COSDocument())


def test_wrong_w_length_raises() -> None:
    stream = _make_stream([1, 2], [0, 1], b"")
    with pytest.raises(PDFParseError):
        PDFXrefStreamParser(stream, COSDocument())


def test_negative_w_raises() -> None:
    stream = _make_stream([1, -1, 1], [0, 1], b"")
    with pytest.raises(PDFParseError):
        PDFXrefStreamParser(stream, COSDocument())


def test_w_sum_over_20_raises() -> None:
    stream = _make_stream([7, 7, 7], [0, 1], b"")
    with pytest.raises(PDFParseError):
        PDFXrefStreamParser(stream, COSDocument())


def test_odd_index_length_raises() -> None:
    stream = _make_stream([1, 2, 1], [0], b"")
    with pytest.raises(PDFParseError):
        PDFXrefStreamParser(stream, COSDocument())


# ---------------------------------------------------------------------------
# 7. FlateDecode body (with / without PNG predictor)
# ---------------------------------------------------------------------------


def test_flate_decoded_body() -> None:
    w = [1, 2, 1]
    rows = [(1, 0x1234, 0), (2, 5, 2), (1, 0x5678, 1)]
    body = _encode_body(w, rows)
    index = [0, 3]
    stream = _make_stream(w, index, body, flate=True)
    got = _run_parser(stream)
    expected = _expected_offsets(_reference_decode(w, index, body))
    assert got == expected
    assert got == {0: 0x1234, 1: -5, 2: 0x5678}


def test_flate_with_png_up_predictor() -> None:
    w = [1, 2, 1]
    columns = w[0] + w[1] + w[2]
    rows = [(1, 0x0101, 0), (1, 0x0202, 0), (1, 0x0303, 0)]
    body = _encode_body(w, rows)
    index = [0, 3]
    stream = _make_stream(
        w, index, body, flate=True, predictor=12, columns=columns
    )
    got = _run_parser(stream)
    assert got == {0: 0x0101, 1: 0x0202, 2: 0x0303}


# ---------------------------------------------------------------------------
# 8. Randomised differential fuzz
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("seed", range(12))
def test_random_differential(seed: int) -> None:
    rng = random.Random(seed)
    w = [rng.randint(0, 2), rng.randint(1, 4), rng.randint(0, 2)]
    # Build a few subsections.
    n_sub = rng.randint(1, 3)
    index: list[int] = []
    rows: list[tuple[int, int, int]] = []
    for _ in range(n_sub):
        start = rng.randint(0, 500)
        count = rng.randint(0, 4)
        index += [start, count]
        for _ in range(count):
            type_ = rng.choice([0, 1, 1, 2])  # bias toward in-use
            if w[0] == 0:
                type_ = 1
            f2 = rng.randint(0, (1 << (8 * w[1])) - 1)
            f3 = rng.randint(0, (1 << (8 * w[2])) - 1) if w[2] else 0
            rows.append((type_, f2, f3))
    if not index or all(c == 0 for c in index[1::2]):
        index = [0, len(rows)] if rows else [0, 0]

    body = _encode_body(w, rows)
    use_flate = rng.random() < 0.5
    stream = _make_stream(w, index, body, flate=use_flate)
    got = _run_parser(stream)
    expected = _expected_offsets(_reference_decode(w, index, body))
    assert got == expected


def test_struct_packed_matches_manual_encode() -> None:
    # Sanity: struct.pack big-endian agrees with our to_bytes encoder for the
    # field widths the parser supports.
    assert struct.pack(">I", 0x01020304) == (0x01020304).to_bytes(4, "big")
    assert PDFXrefStreamParser.parse_value(
        bytearray(struct.pack(">I", 0x01020304)), 0, 4
    ) == 0x01020304
