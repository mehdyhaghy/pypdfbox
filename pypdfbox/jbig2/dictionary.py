from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING

from pypdfbox.jbig2.segment_data import SegmentData

if TYPE_CHECKING:
    from pypdfbox.jbig2.bitmap import Bitmap


class Dictionary(SegmentData):
    """Interface for all JBIG2 dictionaries segments.

    Mirrors ``org.apache.pdfbox.jbig2.Dictionary``, which extends
    :class:`SegmentData`.
    """

    @abstractmethod
    def get_dictionary(self) -> list[Bitmap]:
        """Decode a dictionary segment and return the result.

        :return: A list of :class:`Bitmap`\\ s as a result of the decoding
            process of dictionary segments.

        :raises OSError: if an underlying IO operation fails.
        :raises InvalidHeaderValueException: if the segment header value is invalid.
        :raises IntegerMaxValueException: if the maximum value limit of an integer
            is exceeded.
        """
        raise NotImplementedError
