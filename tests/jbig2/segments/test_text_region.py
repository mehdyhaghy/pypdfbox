"""Hand-written unit tests for the JBIG2 text-region decoder.

Covers ``TextRegion`` flag parsing (7.4.3.1.1 - 7.4.3.1.4), the ``_check_input``
flag normalisation / validation, the symbol-instance placement helper
(``_blit`` reference-corner / transposition geometry), and full end-to-end
arithmetic decoding of a real immediate text region (type 6) sliced out of the
upstream ``.jb2`` test fixtures, with its symbol set supplied by the referred
standalone symbol dictionary (decoded by the already-parity-checked
``SymbolDictionary``).

The end-to-end expectation (region bitmap width/height/row-stride + a SHA-256
over its packed bytes) was captured from this very decoder *after* confirming
bit-exact agreement with the upstream Apache PDFBox ``TextRegion`` (3.0.7) on
the identical byte slices; the live oracle differential lives in
``tests/jbig2/segments/oracle/test_text_region_oracle.py``.

All fixtures here are arithmetic-coded, non-refinement text regions. The Huffman
path and the per-instance refinement path are not exercised by these fixtures.
"""

from __future__ import annotations

import hashlib
import struct
from pathlib import Path

import pytest

from pypdfbox.jbig2.bitmap import Bitmap
from pypdfbox.jbig2.io.image_input_stream import ImageInputStream
from pypdfbox.jbig2.io.sub_input_stream import SubInputStream
from pypdfbox.jbig2.segments.symbol_dictionary import SymbolDictionary
from pypdfbox.jbig2.segments.text_region import TextRegion
from pypdfbox.jbig2.util.combination_operator import CombinationOperator

_FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"

_JBIG2_FILE_MAGIC = bytes([0x97, 0x4A, 0x42, 0x32, 0x0D, 0x0A, 0x1A, 0x0A])


class _StubHeaderNoRt:
    """Segment header whose ``get_rt_segments`` returns ``None``."""

    def get_rt_segments(self) -> None:
        return None


class _StubSdHeader:
    """Synthetic symbol-dictionary header carrying a decoded dictionary."""

    def __init__(self, sd: SymbolDictionary) -> None:
        self._sd = sd

    def get_segment_type(self) -> int:
        return 0

    def get_segment_data(self) -> SymbolDictionary:
        return self._sd


class _StubTextHeader:
    """Synthetic text-region header referring to a single dictionary header."""

    def __init__(self, sd_header: _StubSdHeader) -> None:
        self._rt = [sd_header]

    def get_rt_segments(self) -> list:
        return self._rt


def _segments(jb2_path: Path) -> list[tuple[int, int, int, list[int], int, int]]:
    """Parse the JBIG2 segment headers (7.2) of a file-organised ``.jb2`` stream.

    Returns ``(segment_nr, segment_type, ref_count, refs, data_start, data_len)``
    tuples in stream order.
    """
    d = jb2_path.read_bytes()
    p = 0
    if d[:8] == _JBIG2_FILE_MAGIC:
        file_flags = d[8]
        p = 9
        if not (file_flags & 2):
            p += 4  # number-of-pages field present

    out: list[tuple[int, int, int, list[int], int, int]] = []
    while p < len(d) - 11:
        segment_nr = struct.unpack(">I", d[p : p + 4])[0]
        p += 4
        flag_byte = d[p]
        p += 1
        segment_type = flag_byte & 0x3F
        page_assoc_4 = (flag_byte >> 6) & 1

        rt_flags = d[p]
        count = (rt_flags >> 5) & 7
        if count <= 4:
            p += 1
        else:
            count = struct.unpack(">I", d[p : p + 4])[0] & 0x1FFFFFFF
            p += 4 + ((count + 8) >> 3)

        if segment_nr <= 256:
            rt_size = 1
        elif segment_nr <= 65536:
            rt_size = 2
        else:
            rt_size = 4
        refs: list[int] = []
        for _i in range(count):
            if rt_size == 1:
                refs.append(d[p])
            elif rt_size == 2:
                refs.append(struct.unpack(">H", d[p : p + 2])[0])
            else:
                refs.append(struct.unpack(">I", d[p : p + 4])[0])
            p += rt_size

        p += 4 if page_assoc_4 else 1

        data_length = struct.unpack(">I", d[p : p + 4])[0]
        p += 4
        data_start = p
        out.append((segment_nr, segment_type, count, refs, data_start, data_length))
        p = data_start + data_length

    return out


def _symbol_dict_and_text_region_slices(jb2_path: Path) -> tuple[bytes, bytes]:
    """Return ``(symbol_dict_data, text_region_data)`` of the first matching pair.

    Finds the first standalone (no referred-to segments) type-0 symbol
    dictionary, then the first type-6 immediate text region that refers to it,
    and returns both segment-data slices.
    """
    d = jb2_path.read_bytes()
    segs = _segments(jb2_path)

    sd_nr = None
    sd_slice = None
    for nr, seg_type, count, _refs, ds, dl in segs:
        if seg_type == 0 and count == 0:
            sd_nr = nr
            sd_slice = d[ds : ds + dl]
            break
    assert sd_slice is not None, f"no standalone symbol dictionary in {jb2_path}"

    for _nr, seg_type, _count, refs, ds, dl in segs:
        if seg_type == 6 and sd_nr in refs:
            return sd_slice, d[ds : ds + dl]

    raise AssertionError(f"no immediate text region referring to {sd_nr} in {jb2_path}")


def _decode_symbol_dict(blob: bytes) -> SymbolDictionary:
    sd = SymbolDictionary()
    sd.init(_StubHeaderNoRt(), SubInputStream(ImageInputStream(blob), 0, len(blob)))
    sd.get_dictionary()
    return sd


def _decode_text_region(sd_blob: bytes, tr_blob: bytes) -> Bitmap:
    sd = _decode_symbol_dict(sd_blob)
    text_header = _StubTextHeader(_StubSdHeader(sd))
    tr = TextRegion()
    tr.init(
        text_header, SubInputStream(ImageInputStream(tr_blob), 0, len(tr_blob))
    )
    return tr.get_region_bitmap()


def _bitmap_digest(b: Bitmap) -> str:
    digest = hashlib.sha256()
    digest.update(
        struct.pack(">III", b.get_width(), b.get_height(), b.get_row_stride())
    )
    digest.update(bytes(b.get_byte_array()))
    return digest.hexdigest()


# (fixture, expected width, height, row stride, packed-bytes digest)
_REAL_CASES = [
    (
        "003.jb2",
        2550,
        3305,
        319,
        "7af61722acc8e8ce695201d0cbf16b2511ca9c0c78e0db0bf010d8e8e4b1a7af",
    ),
    (
        "005.jb2",
        2544,
        3330,
        318,
        "a0e4598f36b01b7db9c0a3f4ee555a089df0dd64e37420b852c19e5279117394",
    ),
]


@pytest.mark.parametrize(
    ("fixture", "width", "height", "row_stride", "digest"),
    _REAL_CASES,
    ids=[c[0] for c in _REAL_CASES],
)
def test_decode_real_arithmetic_text_region(fixture, width, height, row_stride, digest):
    sd_blob, tr_blob = _symbol_dict_and_text_region_slices(_FIXTURES / fixture)
    bitmap = _decode_text_region(sd_blob, tr_blob)

    assert bitmap.get_width() == width
    assert bitmap.get_height() == height
    assert bitmap.get_row_stride() == row_stride
    assert _bitmap_digest(bitmap) == digest
    # Some pixels must be black (symbols were placed).
    assert any(b != 0 for b in bitmap.get_byte_array())


def test_decode_is_stable_across_calls():
    sd_blob, tr_blob = _symbol_dict_and_text_region_slices(_FIXTURES / "003.jb2")
    first = _bitmap_digest(_decode_text_region(sd_blob, tr_blob))
    second = _bitmap_digest(_decode_text_region(sd_blob, tr_blob))
    assert first == second


def test_header_parsing_real_region():
    sd_blob, tr_blob = _symbol_dict_and_text_region_slices(_FIXTURES / "003.jb2")
    sd = _decode_symbol_dict(sd_blob)
    tr = TextRegion()
    tr.init(
        _StubTextHeader(_StubSdHeader(sd)),
        SubInputStream(ImageInputStream(tr_blob), 0, len(tr_blob)),
    )
    # Arithmetic-coded, non-refinement.
    assert not tr.is_huffman_encoded
    # The symbol count matches the dictionary's exported symbols.
    assert tr.amount_of_symbols == len(sd.get_dictionary())
    assert tr.amount_of_symbol_instances > 0


# ----------------------------------------------------------------------------
# _check_input flag normalisation / validation
# ----------------------------------------------------------------------------


def _fresh() -> TextRegion:
    return TextRegion()


def test_check_input_no_refinement_forces_sbr_template_zero():
    tr = _fresh()
    tr.use_refinement = False
    tr.sbr_template = 1
    tr._check_input()
    assert tr.sbr_template == 0


@pytest.mark.parametrize(
    "field",
    [
        "sb_huff_fs",
        "sb_huff_rd_width",
        "sb_huff_rd_height",
        "sb_huff_rdx",
        "sb_huff_rdy",
    ],
)
def test_check_input_rejects_huffman_flag_value_2(field):
    from pypdfbox.jbig2.err.invalid_header_value_exception import (
        InvalidHeaderValueException,
    )

    tr = _fresh()
    setattr(tr, field, 2)
    with pytest.raises(InvalidHeaderValueException):
        tr._check_input()


def test_check_input_no_refinement_clears_huffman_refinement_flags():
    tr = _fresh()
    tr.use_refinement = False
    tr.sb_huff_r_size = 1
    tr.sb_huff_rdy = 1
    tr.sb_huff_rdx = 1
    tr.sb_huff_rd_width = 1
    tr.sb_huff_rd_height = 1
    tr._check_input()
    assert tr.sb_huff_r_size == 0
    assert tr.sb_huff_rdy == 0
    assert tr.sb_huff_rdx == 0
    assert tr.sb_huff_rd_width == 0
    assert tr.sb_huff_rd_height == 0


# ----------------------------------------------------------------------------
# _blit reference-corner / transposition geometry (6.4.5 vii-x)
# ----------------------------------------------------------------------------


def _blit_at(reference_corner: int, transposed: int, current_s_start: int, t: int):
    """Run ``_blit`` against a fresh 16x16 region with a single 3x4 symbol.

    Returns ``(region, current_s_after)``.
    """
    tr = _fresh()
    tr.region_bitmap = Bitmap(16, 16)
    tr.combination_operator = CombinationOperator.OR
    tr.reference_corner = reference_corner
    tr.is_transposed = transposed
    tr.current_s = current_s_start

    sym = Bitmap(3, 4)  # width 3, height 4
    sym.fill_bitmap(0xFF)

    tr._blit(sym, t)
    return tr.region_bitmap, tr.current_s


def test_blit_topleft_places_at_s_t_and_advances_by_width():
    # referenceCorner 1 == TL, not transposed: place at (s, t), advance by w-1.
    region, current_s = _blit_at(
        reference_corner=1, transposed=0, current_s_start=2, t=5
    )
    # Upper-left corner of the symbol lands at (2, 5).
    assert region.get_pixel(2, 5) == 1
    assert region.get_pixel(4, 8) == 1  # 3 wide, 4 tall ⇒ (2..4, 5..8)
    # current_s advanced by width - 1.
    assert current_s == 2 + (3 - 1)


def test_blit_bottomleft_offsets_t_by_height():
    # referenceCorner 0 == BL, not transposed: t -= height - 1, then place.
    region, _ = _blit_at(reference_corner=0, transposed=0, current_s_start=0, t=10)
    # Bottom-left corner at (0, 10) ⇒ top at y = 10 - (4 - 1) = 7.
    assert region.get_pixel(0, 7) == 1
    assert region.get_pixel(2, 10) == 1


def test_blit_topright_pre_advances_then_offsets_s():
    # referenceCorner 3 == TR, not transposed: pre-add width-1 to s, then s -= w-1.
    region, current_s = _blit_at(
        reference_corner=3, transposed=0, current_s_start=5, t=0
    )
    # current_s pre-advanced by width - 1 ⇒ 7; placement s = 7 - (3-1) = 5.
    assert region.get_pixel(5, 0) == 1
    assert current_s == 7


def test_blit_transposed_swaps_s_and_t():
    # transposed, referenceCorner 1 (TL): s and t are swapped before placement.
    region, _ = _blit_at(reference_corner=1, transposed=1, current_s_start=3, t=6)
    # current_s starts at 3 (TL transposed does not pre-advance); after swap the
    # symbol's upper-left lands at (t=6, s=3) ⇒ x=6, y=3.
    assert region.get_pixel(6, 3) == 1


# ----------------------------------------------------------------------------
# Symbol-ID Huffman run-code-length table (7.4.3.1.7)
# ----------------------------------------------------------------------------


def test_symbol_id_code_lengths_builds_table():
    # 35 four-bit run-code prefix lengths, then the per-symbol code lengths.
    # Build a tiny bitstream: all 35 run-code lengths zero except entry 1 which
    # gets prefix length 1, then two symbols each coded with the single 1-bit
    # code (value 0 ⇒ "0").
    import io

    bits: list[int] = []

    def emit(value: int, n: int) -> None:
        for i in range(n - 1, -1, -1):
            bits.append((value >> i) & 1)

    # 35 run-code prefix lengths (4 bits each). Give entry "1" prefix length 1
    # (so the run-code value 1 decodes to a 1-bit Huffman code), all others 0.
    for i in range(35):
        emit(1 if i == 1 else 0, 4)

    # With a single code of prefix length 1, its assigned bit pattern is "0".
    # Decoding run-code value 1 (< 32) sets the symbol's code length to 1.
    # Two symbols ⇒ emit "0" twice.
    emit(0, 1)
    emit(0, 1)

    # Pad to a byte boundary.
    while len(bits) % 8 != 0:
        bits.append(0)
    raw = bytearray()
    for i in range(0, len(bits), 8):
        byte = 0
        for b in bits[i : i + 8]:
            byte = (byte << 1) | b
        raw.append(byte)

    tr = _fresh()
    tr.amount_of_symbols = 2
    tr.sub_input_stream = SubInputStream(
        ImageInputStream(io.BytesIO(bytes(raw))), 0, len(raw)
    )
    tr._symbol_id_code_lengths()
    assert tr.symbol_code_table is not None
