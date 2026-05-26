from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pypdfbox.jbig2.io.sub_input_stream import SubInputStream
    from pypdfbox.jbig2.segment_header import SegmentHeader


class SegmentData(ABC):
    """Interface for all data parts of segments.

    Mirrors ``org.apache.pdfbox.jbig2.SegmentData``. Implemented as an abstract
    base class; every concrete segment type implements :meth:`init`.
    """

    @abstractmethod
    def init(self, header: SegmentHeader, sis: SubInputStream) -> None:
        """Parse the stream and read information of header.

        :param header: The segments' header (to make referred-to segments
            available in data part).
        :param sis: Wrapped ``ImageInputStream`` into ``SubInputStream``.

        :raises InvalidHeaderValueException: if the segment header value is invalid.
        :raises IntegerMaxValueException: if the maximum value limit of an integer
            is exceeded.
        :raises OSError: if an underlying IO operation fails.
        """
        raise NotImplementedError
