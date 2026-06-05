"""Regression tests for negative-reference-offset generic refinement decode.

Wave 1488 fixed a Java-vs-Python remainder divergence in
``GenericRefinementRegionDecodingProcedure._decode_template``: the context-shift
selector ``referenceDX % 8`` was evaluated with Python's floored remainder
(``-1 % 8 == 7``) instead of Java's truncated remainder (``-1 % 8 == -1``). On a
JBIG2 stream with a large (805-symbol) dictionary whose text-region refinement
instances carry a negative reference offset (``(RDW >> 1) + RDX < 0``), the
divergent shift selected the wrong context branch, corrupted a refinement
bitmap, desynced the shared arithmetic decoder and ultimately decoded an
out-of-range symbol id (``IndexError``).

The ``20123110001.jb2`` fixture is the upstream pdfbox-jbig2 reproducer; the
end-to-end bit-exact assertion against Apache PDFBox lives in
``tests/jbig2/oracle/test_jbig2_page_oracle.py``. These tests pin the decoded
page so the fix is guarded even when the live Java oracle is unavailable, and
unit-test the ``_java_mod`` helper directly.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from pypdfbox.jbig2.decoder.generic_refinement_region_decoding_procedure import (
    _java_mod,
)
from pypdfbox.jbig2.io.image_input_stream import ImageInputStream
from pypdfbox.jbig2.jbig2_document import JBIG2Document

_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"

# Captured from the post-fix decode, verified bit-exact against Apache PDFBox
# 3.0.7 (Jbig2PageProbe) on 20123110001.jb2.
_EXPECTED_WIDTH = 2550
_EXPECTED_HEIGHT = 3345
_EXPECTED_ROW_STRIDE = 319
_EXPECTED_SHA256 = (
    "7547580c5befce84225309ba60ffdea373422ead4e08db4f7172bba430dac9fd"
)


def test_large_symbol_dictionary_page_decodes_bit_exact():
    data = (_FIXTURES / "20123110001.jb2").read_bytes()
    bitmap = JBIG2Document(ImageInputStream(data)).get_page(1).get_bitmap()

    assert bitmap.get_width() == _EXPECTED_WIDTH
    assert bitmap.get_height() == _EXPECTED_HEIGHT
    assert bitmap.get_row_stride() == _EXPECTED_ROW_STRIDE

    packed = bytes(bitmap.get_byte_array())
    assert hashlib.sha256(packed).hexdigest() == _EXPECTED_SHA256


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [
        # Java's % follows the sign of the dividend (truncated toward zero),
        # unlike Python's % which follows the divisor.
        (-1, 8, -1),
        (-3, 8, -3),
        (-8, 8, 0),
        (-9, 8, -1),
        (7, 8, 7),
        (0, 8, 0),
        (-5, 8, -5),
    ],
)
def test_java_mod_matches_truncated_remainder(a, b, expected):
    assert _java_mod(a, b) == expected


def test_java_mod_diverges_from_python_for_negative_dividend():
    # The bug: Python's floored remainder yields 7 here; Java yields -1.
    assert (-1) % 8 == 7
    assert _java_mod(-1, 8) == -1
