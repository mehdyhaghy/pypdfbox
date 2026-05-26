"""Hand-written unit tests for the JBIG2 symbol-dictionary decoder.

Covers ``SymbolDictionary`` flag parsing (7.4.2.1.1 - 7.4.2.1.5), the
``_check_input`` flag normalisation, the SBSYMCODELEN computation (6.5.8.2.3),
the export-flag run-length expansion (6.5.10), and full end-to-end arithmetic
decoding of real standalone (no referred-to segments) symbol-dictionary
segments sliced out of the upstream ``.jb2`` test fixtures.

The end-to-end expectations (exported symbol count + a SHA-256 over every
symbol's width/height/row-stride and packed bytes) were captured from this very
decoder *after* confirming bit-exact agreement with the upstream Apache PDFBox
``SymbolDictionary`` (3.0.7) on the identical byte slices; the live oracle
differential lives in
``tests/jbig2/segments/oracle/test_symbol_dictionary_oracle.py``.

All fixtures here are arithmetic-coded, non-refinement, SDTEMPLATE 0 (the direct
generic-region path, 6.5.8.1). The Huffman path and the text-region aggregate
path are not exercised by these standalone dictionaries; the aggregate path is
stubbed pending the ``TextRegion`` port.
"""

from __future__ import annotations

import hashlib
import struct
from pathlib import Path

import pytest

from pypdfbox.jbig2.io.image_input_stream import ImageInputStream
from pypdfbox.jbig2.io.sub_input_stream import SubInputStream
from pypdfbox.jbig2.segments.symbol_dictionary import SymbolDictionary

_FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"

_JBIG2_FILE_MAGIC = bytes([0x97, 0x4A, 0x42, 0x32, 0x0D, 0x0A, 0x1A, 0x0A])


class _StubHeader:
    """Minimal segment header whose ``get_rt_segments`` returns ``None``.

    A standalone symbol dictionary refers to no other segments, so the decoder
    only ever calls ``get_rt_segments()`` (returning ``None`` ⇒ no imported
    symbols). This avoids needing the not-yet-ported JBIG2 document machinery.
    """

    def get_rt_segments(self) -> None:
        return None


def _first_standalone_symbol_dict(jb2_path: Path) -> bytes:
    """Return the segment-data slice of the first standalone symbol dictionary.

    Scans the JBIG2 segment headers (7.2) of a file-organised ``.jb2`` stream
    and returns the data part of the first type-0 (symbol dictionary) segment
    that refers to no other segments.
    """
    d = jb2_path.read_bytes()
    p = 0
    if d[:8] == _JBIG2_FILE_MAGIC:
        file_flags = d[8]
        p = 9
        if not (file_flags & 2):
            p += 4  # number-of-pages field present

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
        p += count * rt_size

        p += 4 if page_assoc_4 else 1

        data_length = struct.unpack(">I", d[p : p + 4])[0]
        p += 4
        data_start = p

        if segment_type == 0 and count == 0:
            return d[data_start : data_start + data_length]
        p = data_start + data_length

    raise AssertionError(f"no standalone symbol dictionary in {jb2_path}")


def _decode(blob: bytes) -> SymbolDictionary:
    sd = SymbolDictionary()
    sd.init(_StubHeader(), SubInputStream(ImageInputStream(blob), 0, len(blob)))
    return sd


def _symbols_digest(symbols: list) -> str:
    digest = hashlib.sha256()
    for b in symbols:
        digest.update(
            struct.pack(">III", b.get_width(), b.get_height(), b.get_row_stride())
        )
        digest.update(bytes(b.get_byte_array()))
    return digest.hexdigest()


# (fixture, expected exported count, expected symbols digest)
_REAL_CASES = [
    (
        "003.jb2",
        99,
        "9a5f5afd3aed985e477b44db166a170e6b713ea81628ad3fc265d841484d0de2",
    ),
    (
        "005.jb2",
        305,
        "f6da3ebacfa8383df22146f5e2f1835d8714746279a8c6085fe063c55310513d",
    ),
]


@pytest.mark.parametrize(
    ("fixture", "expected_count", "expected_digest"),
    _REAL_CASES,
    ids=[c[0] for c in _REAL_CASES],
)
def test_decode_real_arithmetic_dictionary(fixture, expected_count, expected_digest):
    blob = _first_standalone_symbol_dict(_FIXTURES / fixture)
    sd = _decode(blob)

    # Flags: arithmetic, no refinement-aggregation, SDTEMPLATE 0.
    assert not sd.is_huffman_encoded
    assert not sd.use_refinement_aggregation
    assert sd.sd_template == 0

    symbols = sd.get_dictionary()
    assert len(symbols) == expected_count
    assert _symbols_digest(symbols) == expected_digest


def test_get_dictionary_is_idempotent():
    blob = _first_standalone_symbol_dict(_FIXTURES / "003.jb2")
    sd = _decode(blob)
    first = sd.get_dictionary()
    # Second call returns the cached list (export_symbols already set).
    assert sd.get_dictionary() is first


def test_header_parses_at_pixels_for_template0():
    blob = _first_standalone_symbol_dict(_FIXTURES / "003.jb2")
    sd = _decode(blob)
    # SDTEMPLATE 0 ⇒ 4 AT pixel pairs read (7.4.2.1.2).
    assert sd.sd_at_x is not None
    assert len(sd.sd_at_x) == 4
    assert len(sd.sd_at_y) == 4
    # Refinement AT pixels only read when refinement-aggregation is on.
    assert sd.sdr_at_x is None


def test_amount_fields_read():
    blob = _first_standalone_symbol_dict(_FIXTURES / "003.jb2")
    sd = _decode(blob)
    assert sd.amount_of_new_symbols == 99
    assert sd.amount_of_export_symbolss == 99
    assert sd.amount_of_imported_symbols == 0


# ----------------------------------------------------------------------------
# _check_input flag normalisation (7.4.x consistency rules)
# ----------------------------------------------------------------------------


def _fresh() -> SymbolDictionary:
    return SymbolDictionary()


def test_check_input_huffman_forces_sd_template_zero():
    sd = _fresh()
    sd.is_huffman_encoded = True
    sd.sd_template = 3
    sd._check_input()
    assert sd.sd_template == 0


def test_check_input_huffman_no_refagg_clears_context_flags():
    sd = _fresh()
    sd.is_huffman_encoded = True
    sd.use_refinement_aggregation = False
    sd.is_coding_context_retained = True
    sd.is_coding_context_used = True
    sd._check_input()
    assert not sd.is_coding_context_retained
    assert not sd.is_coding_context_used


def test_check_input_arithmetic_clears_huffman_selections():
    sd = _fresh()
    sd.is_huffman_encoded = False
    sd.sd_huff_bm_size_selection = 1
    sd.sd_huff_decode_width_selection = 1
    sd.sd_huff_decode_height_selection = 1
    sd._check_input()
    assert sd.sd_huff_bm_size_selection == 0
    assert sd.sd_huff_decode_width_selection == 0
    assert sd.sd_huff_decode_height_selection == 0


def test_check_input_no_refagg_forces_sdr_template_zero():
    sd = _fresh()
    sd.use_refinement_aggregation = False
    sd.sdr_template = 1
    sd._check_input()
    assert sd.sdr_template == 0


def test_check_input_clears_agg_inst_selection_when_not_huffman_refagg():
    sd = _fresh()
    sd.is_huffman_encoded = False
    sd.use_refinement_aggregation = True
    sd.sd_huff_agg_instance_selection = 1
    sd._check_input()
    assert sd.sd_huff_agg_instance_selection == 0


# ----------------------------------------------------------------------------
# SBSYMCODELEN (6.5.8.2.3)
# ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("imported", "new", "huffman", "expected"),
    [
        # ceil(log2(n)); Huffman clamps to a minimum of 1.
        (0, 2, False, 1),
        (0, 4, False, 2),
        (0, 5, False, 3),
        (0, 1, False, 0),  # log2(1) == 0
        (0, 1, True, 1),  # Huffman minimum
        (3, 5, False, 3),  # ceil(log2(8)) == 3
    ],
)
def test_get_sb_sym_code_len(imported, new, huffman, expected):
    sd = _fresh()
    sd.amount_of_imported_symbols = imported
    sd.amount_of_new_symbols = new
    sd.is_huffman_encoded = huffman
    assert sd._get_sb_sym_code_len() == expected


# ----------------------------------------------------------------------------
# Export-flag run-length expansion (6.5.10) and validation
# ----------------------------------------------------------------------------


class _FakeIntDecoder:
    """Returns a scripted sequence of values from ``decode()``."""

    def __init__(self, values):
        self._values = list(values)

    def decode(self, _cx):
        return self._values.pop(0)


def test_get_to_export_flags_run_length():
    sd = _fresh()
    sd.is_huffman_encoded = False
    sd.amount_of_imported_symbols = 0
    sd.amount_of_new_symbols = 5
    # runs: 2 not-exported, 3 exported  → flags [0,0,1,1,1]
    sd.i_decoder = _FakeIntDecoder([2, 3])
    assert sd._get_to_export_flags() == [0, 0, 1, 1, 1]


def test_get_to_export_flags_all_exported_first_run():
    sd = _fresh()
    sd.is_huffman_encoded = False
    sd.amount_of_imported_symbols = 0
    sd.amount_of_new_symbols = 4
    # first run 0 (none not-exported), then 4 exported → [1,1,1,1]
    sd.i_decoder = _FakeIntDecoder([0, 4])
    assert sd._get_to_export_flags() == [1, 1, 1, 1]


def test_get_to_export_flags_rejects_negative_counts():
    sd = _fresh()
    sd.amount_of_imported_symbols = -1
    sd.amount_of_new_symbols = 1
    from pypdfbox.jbig2.err.invalid_header_value_exception import (
        InvalidHeaderValueException,
    )

    with pytest.raises(InvalidHeaderValueException):
        sd._get_to_export_flags()


def test_get_to_export_flags_rejects_overlong_run():
    sd = _fresh()
    sd.is_huffman_encoded = False
    sd.amount_of_imported_symbols = 0
    sd.amount_of_new_symbols = 3
    sd.i_decoder = _FakeIntDecoder([99])  # > total
    from pypdfbox.jbig2.err.invalid_header_value_exception import (
        InvalidHeaderValueException,
    )

    with pytest.raises(InvalidHeaderValueException):
        sd._get_to_export_flags()


# ----------------------------------------------------------------------------
# Set exported symbols mixes imported + new (6.5.10 6-8)
# ----------------------------------------------------------------------------


def test_set_exported_symbols_mixes_imported_and_new():
    sd = _fresh()
    sd.amount_of_imported_symbols = 2
    sd.amount_of_new_symbols = 2
    sd.import_symbols = ["imp0", "imp1"]
    sd.new_symbols = ["new0", "new1"]
    # export imported[1] and new[0]
    sd._set_exported_symbols([0, 1, 1, 0])
    assert sd.export_symbols == ["imp1", "new0"]
