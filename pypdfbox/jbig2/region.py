from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING

from pypdfbox.jbig2.segment_data import SegmentData

if TYPE_CHECKING:
    from pypdfbox.jbig2.bitmap import Bitmap
    from pypdfbox.jbig2.segments.region_segment_information import (
        RegionSegmentInformation,
    )


class Region(SegmentData):
    """Interface for all JBIG2 region segments.

    Mirrors ``org.apache.pdfbox.jbig2.Region``, which extends
    :class:`SegmentData`.
    """

    @abstractmethod
    def get_region_bitmap(self) -> Bitmap:
        """Decode and return a region's content.

        :return: The decoded region as :class:`Bitmap`.

        :raises OSError: if an underlying IO operation fails.
        :raises IntegerMaxValueException: if the maximum value limit of an integer
            is exceeded.
        :raises InvalidHeaderValueException: if the segment header value is invalid.
        """
        raise NotImplementedError

    @abstractmethod
    def get_region_info(self) -> RegionSegmentInformation:
        """Return the :class:`RegionSegmentInformation`."""
        raise NotImplementedError
