from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.jbig2.segment_data import SegmentData

if TYPE_CHECKING:
    from pypdfbox.jbig2.io.sub_input_stream import SubInputStream
    from pypdfbox.jbig2.segment_header import SegmentHeader


class Profiles(SegmentData):
    """TODO: This class is not implemented yet and empty. Wait for use cases.

    Mirrors ``org.apache.pdfbox.jbig2.segments.Profiles``.
    """

    def init(self, header: SegmentHeader, sis: SubInputStream) -> None:
        pass
