"""Live differential oracle for the JBIG2 MMR (CCITT Group-4) decoder.

Drives the upstream Apache PDFBox ``MMRDecompressor`` via
``oracle/probes/MmrProbe.java`` on fixed CCITT-G4 strips and asserts that
pypdfbox's ``MMRDecompressor`` produces the IDENTICAL decoded bitmap (width,
height, row stride, and every packed byte). This is the gold-standard parity
check for the 2-D READ state machine: pass / horizontal / vertical modes,
reference-line tracking, makeup runs, and the little-endian two-level code
tables.

The CCITT-G4 strips are generated on the fly via Pillow/libtiff
(``Image.save(..., compression="group4")``) so the inputs are real, spec-valid
Group-4 data rather than hand-rolled bit patterns.
"""

from __future__ import annotations

import pytest

from pypdfbox.jbig2.decoder.mmr.mmr_decompressor import MMRDecompressor
from pypdfbox.jbig2.io.image_input_stream import ImageInputStream
from tests.jbig2.decoder.mmr.test_mmr_decompressor import g4_strip
from tests.oracle.harness import requires_oracle, run_probe_text


def _py_decode(strip_hex: str, width: int, height: int) -> str:
    """Decode with pypdfbox, formatted like the probe: 'w h stride hexbytes'."""
    iis = ImageInputStream(bytes.fromhex(strip_hex))
    bitmap = MMRDecompressor(width, height, iis).uncompress()
    return (
        f"{bitmap.get_width()} {bitmap.get_height()} {bitmap.get_row_stride()} "
        f"{bytes(bitmap.get_byte_array()).hex()}"
    )


def _rectangle(width, height, x0, y0, x1, y1):
    return [(x, y) for y in range(y0, y1) for x in range(x0, x1)]


def _stripes(width, height):
    return [(x, y) for y in range(height) for x in range(0, width, 2)]


def _diagonal(width, height):
    return [(i, i) for i in range(min(width, height))]


def _full(width, height):
    return [(x, y) for y in range(height) for x in range(width)]


def _checker(width, height):
    return [(x, y) for y in range(height) for x in range(width) if (x + y) & 1]


# (name, width, height, black_pixels_factory)
_CASES = [
    ("rect16x8", 16, 8, lambda w, h: _rectangle(w, h, 4, 2, 12, 6)),
    ("stripes13x5", 13, 5, _stripes),
    ("diag20x20", 20, 20, _diagonal),
    ("black24x4", 24, 4, _full),
    ("wide200x3", 200, 3, lambda w, h: _rectangle(w, h, 50, 0, 170, 3)),
    ("checker17x9", 17, 9, _checker),
    ("rect100x40", 100, 40, lambda w, h: _rectangle(w, h, 10, 5, 90, 35)),
    ("single_dot1x1", 1, 1, lambda w, h: [(0, 0)]),
]


@requires_oracle
@pytest.mark.parametrize(
    ("name", "width", "height", "factory"),
    _CASES,
    ids=[c[0] for c in _CASES],
)
def test_mmr_decoder_matches_pdfbox(name, width, height, factory):
    strip_hex = g4_strip(width, height, factory(width, height))

    java_out = run_probe_text("MmrProbe", strip_hex, str(width), str(height)).strip()
    py_out = _py_decode(strip_hex, width, height)

    assert py_out == java_out
