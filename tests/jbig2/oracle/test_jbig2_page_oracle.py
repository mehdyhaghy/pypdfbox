"""Live end-to-end differential oracle for the JBIG2 page decoder.

Drives the upstream Apache PDFBox ``JBIG2Document`` -> ``JBIG2Page.getBitmap()``
pipeline via ``oracle/probes/Jbig2PageProbe.java`` on real embedded/standalone
JBIG2 streams and asserts that pypdfbox's
``JBIG2Document(...).get_page(1).get_bitmap()`` produces the IDENTICAL composed
page bitmap (width, height, row stride, and every packed byte).

This is the gold-standard parity check for the full decode-and-compose path: it
exercises the file-header / segment-sequence parsing, referred-to-segment
resolution, the symbol-dictionary + text-region decoders, and the page
composition (region blit / striping) end to end. Because every decoder feeding
the page is deterministic, a bit-exact page bitmap proves the integration wiring
(dispatch, globals, page buffer, combination operator) matches upstream.

Coverage:

* ``003.jb2`` / ``005.jb2`` / ``006.jb2`` — standalone organisation (the file
  begins with the JBIG2 file header). 006 is multi-page; page 1 is asserted.
* ``21.jb2`` + ``21.glob`` — embedded organisation: bare segments with no file
  header, the symbol dictionary supplied as a separate ``JBIG2Globals`` stream,
  and a striped page (end-of-stripe + text region) composition.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.jbig2.io.image_input_stream import ImageInputStream
from pypdfbox.jbig2.jbig2_document import JBIG2Document
from tests.oracle.harness import requires_oracle, run_probe_text

_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def _format_bitmap(bitmap) -> str:
    """Format a Bitmap like the probe: 'width height stride hexbytes'."""
    return (
        f"{bitmap.get_width()} {bitmap.get_height()} {bitmap.get_row_stride()} "
        f"{bytes(bitmap.get_byte_array()).hex()}"
    )


def _py_decode(data: bytes, page_number: int, globals_data: bytes | None) -> str:
    globals_segments = None
    if globals_data is not None:
        globals_doc = JBIG2Document(ImageInputStream(globals_data))
        globals_segments = globals_doc.get_global_segments()
    document = JBIG2Document(ImageInputStream(data), globals_segments)
    bitmap = document.get_page(page_number).get_bitmap()
    return _format_bitmap(bitmap)


# (name, jb2 filename, page number, optional globals filename)
_STANDALONE_CASES = [
    ("003", "003.jb2", 1, None),
    ("005", "005.jb2", 1, None),
    ("006_page1", "006.jb2", 1, None),
]


@requires_oracle
@pytest.mark.parametrize(
    ("name", "filename", "page_number", "globals_filename"),
    _STANDALONE_CASES,
    ids=[c[0] for c in _STANDALONE_CASES],
)
def test_standalone_page_matches_pdfbox(name, filename, page_number, globals_filename):
    data = (_FIXTURES / filename).read_bytes()
    java = run_probe_text(
        "Jbig2PageProbe", data.hex(), str(page_number)
    ).strip()
    py = _py_decode(data, page_number, None)
    assert py == java


@requires_oracle
def test_embedded_page_with_globals_matches_pdfbox():
    """Embedded organisation: bare segments + separate globals + striped page."""
    data = (_FIXTURES / "21.jb2").read_bytes()
    globals_data = (_FIXTURES / "21.glob").read_bytes()
    java = run_probe_text(
        "Jbig2PageProbe", data.hex(), "1", globals_data.hex()
    ).strip()
    py = _py_decode(data, 1, globals_data)
    assert py == java
