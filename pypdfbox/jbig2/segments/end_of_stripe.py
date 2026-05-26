from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.jbig2.segment_data import SegmentData

if TYPE_CHECKING:
    from pypdfbox.jbig2.io.sub_input_stream import SubInputStream
    from pypdfbox.jbig2.segment_header import SegmentHeader


class EndOfStripe(SegmentData):
    """Flags an end of stripe (see JBIG2 ISO standard, 7.4.9).

    Mirrors ``org.apache.pdfbox.jbig2.segments.EndOfStripe``.
    """

    def __init__(self) -> None:
        self.sub_input_stream: SubInputStream | None = None
        self.line_number = 0

    def _parse_header(self) -> None:
        self.line_number = int(self.sub_input_stream.read_bits(32) & 0xFFFFFFFF)

    def init(self, header: SegmentHeader, sis: SubInputStream) -> None:
        self.sub_input_stream = sis
        self._parse_header()

    def get_line_number(self) -> int:
        return self.line_number
