"""Live differential oracle test for the JBIG2 SegmentHeader parser.

Drives the upstream Apache PDFBox ``SegmentHeader`` (via the bundled app jar) on
a crafted segment-header stream and asserts pypdfbox parses the identical fields
for every header. Skipped automatically when the oracle jar / JDK is absent.
"""

from __future__ import annotations

from pypdfbox.jbig2.io.image_input_stream import ImageInputStream
from pypdfbox.jbig2.io.sub_input_stream import SubInputStream
from pypdfbox.jbig2.segment_header import SEQUENTIAL, SegmentHeader
from tests.oracle.harness import requires_oracle, run_probe_text

# Same crafted three-header stream used by the hand-written tests.
_FULL_HEX = (
    "0000000030000100000013"
    "00000000000000000000000000000000000000"
    "00000001e6000000000200000005"
    "0000000000"
    "0000000232000100000004"
    "00003039"
)
_COUNT = 3


def _pypdfbox_rows(stream: bytes, count: int) -> list[tuple[int, ...]]:
    sis = SubInputStream(ImageInputStream(stream), 0, len(stream))
    rows = []
    offset = 0
    for _ in range(count):
        header = SegmentHeader(None, sis, offset, SEQUENTIAL)
        rows.append(
            (
                header.get_segment_nr(),
                header.get_segment_type(),
                header.get_page_association(),
                header.get_retain_flag(),
                header.get_segment_header_length(),
                header.get_segment_data_length(),
                header.get_segment_data_start_offset(),
            )
        )
        offset = (
            header.get_segment_data_start_offset() + header.get_segment_data_length()
        )
    return rows


def _parse_oracle(text: str) -> list[tuple[int, ...]]:
    rows = []
    for line in text.strip().splitlines():
        rows.append(tuple(int(field) for field in line.split()))
    return rows


@requires_oracle
def test_segment_headers_match_pdfbox():
    java_text = run_probe_text("SegHeaderProbe", _FULL_HEX, str(_COUNT))
    java_rows = _parse_oracle(java_text)
    py_rows = _pypdfbox_rows(bytes.fromhex(_FULL_HEX), _COUNT)
    assert py_rows == java_rows
