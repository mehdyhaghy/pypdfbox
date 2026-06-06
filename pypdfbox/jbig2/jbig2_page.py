from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.jbig2.bitmap import Bitmap
from pypdfbox.jbig2.image.bitmaps import Bitmaps
from pypdfbox.jbig2.region import Region
from pypdfbox.jbig2.segments.end_of_stripe import EndOfStripe
from pypdfbox.jbig2.segments.generic_refinement_region import GenericRefinementRegion

if TYPE_CHECKING:
    from pypdfbox.jbig2.jbig2_document import JBIG2Document
    from pypdfbox.jbig2.segment_data import SegmentData
    from pypdfbox.jbig2.segment_header import SegmentHeader
    from pypdfbox.jbig2.segments.page_information import PageInformation
    from pypdfbox.jbig2.util.combination_operator import CombinationOperator

def _to_signed_int(value: int) -> int:
    """Interpret the low 32 bits of ``value`` as a signed Java ``int``."""
    value &= 0xFFFFFFFF
    return value - 0x100000000 if value >= 0x80000000 else value


# Region segment types that contribute a bitmap to the page buffer.
_REGION_SEGMENT_TYPES = frozenset(
    {
        6,  # Immediate text region
        7,  # Immediate lossless text region
        22,  # Immediate halftone region
        23,  # Immediate lossless halftone region
        38,  # Immediate generic region
        39,  # Immediate lossless generic region
        42,  # Immediate generic refinement region
        43,  # Immediate lossless generic refinement region
    }
)


class JBIG2Page:
    """Represents a JBIG2 page.

    Mirrors ``org.apache.pdfbox.jbig2.JBIG2Page``. Composes the page bitmap from
    its region segments: creates the page buffer from the page-information
    default pixel value, then composes each region's ``get_region_bitmap()`` into
    it via :meth:`Bitmaps.blit` at the region x/y location with the region
    combination operator (handling both normal and striped pages).
    """

    def __init__(self, document: JBIG2Document, page_number: int) -> None:
        self.document = document

        # NOTE: page number != segmentList index.
        self.page_number = page_number

        # This map contains all segments of this page, sorted by segment number
        # in ascending order.
        self.segments: dict[int, SegmentHeader] = {}

        # The page bitmap that represents the page buffer.
        self.page_bitmap: Bitmap | None = None

        self.final_height = 0
        self.final_width = 0
        self.resolution_x = 0
        self.resolution_y = 0

    def get_segment(self, number: int) -> SegmentHeader | None:
        """Search for a segment specified by its number.

        Returns the retrieved :class:`SegmentHeader` or ``None`` if not
        available (falling back to the document's global segments).
        """
        s = self.segments.get(number)
        if s is not None:
            return s

        if self.document is not None:
            return self.document.get_global_segment(number)
        return None

    def get_page_information_segment(self) -> SegmentHeader | None:
        """Return the associated page-information segment (type 48), or None."""
        for s in self.segments.values():
            if s.get_segment_type() == 48:
                return s
        return None

    def get_bitmap(self) -> Bitmap:
        """Return the decoded page bitmap, composing it on first access.

        :raises JBIG2Exception: on a malformed segment.
        :raises OSError: if an underlying IO operation fails.
        """
        if self.page_bitmap is None:
            self._compose_page_bitmap()
        return self.page_bitmap

    def _compose_page_bitmap(self) -> None:
        """Compose the segments' bitmaps to a page and store it as a Bitmap."""
        if self.page_number > 0:
            # Page 79, 1) Decoding the page information segment.
            page_information: PageInformation = (
                self.get_page_information_segment().get_segment_data()
            )
            self._create_page(page_information)
            self._clear_segment_data()

    def _create_page(self, page_information: PageInformation) -> None:
        # Upstream stores the page height as a signed Java int, so an unknown
        # height (0xffffffff) compares equal to -1. PageInformation.get_height()
        # returns the unsigned value, so reinterpret it as a signed 32-bit int
        # here to mirror the upstream "!= -1" test exactly.
        signed_height = _to_signed_int(page_information.get_height())
        if not page_information.is_striped() or signed_height != -1:
            # Page 79, 4).
            self._create_normal_page(page_information)
        else:
            # Striped page with an unknown (0xffffffff) height. No JBIG2 corpus
            # fixture exercises this combination, and a striped page cannot be
            # hand-built without real arithmetic-coded stripe regions, so the
            # striped-compose path stays fixture-starved (see _create_striped_page).
            self._create_striped_page(page_information)  # pragma: no cover

    def _create_normal_page(self, page_information: PageInformation) -> None:
        self.page_bitmap = Bitmap(
            page_information.get_width(), page_information.get_height()
        )

        # Page 79, 3) If the default pixel value is not 0, fill byte with 0xff.
        if page_information.get_default_pixel_value() != 0:
            self.page_bitmap.fill_bitmap(0xFF)

        for s in self.segments.values():
            # Page 79, 5).
            if s.get_segment_type() in _REGION_SEGMENT_TYPES:
                r: Region = s.get_segment_data()

                if isinstance(r, GenericRefinementRegion):
                    r.set_page_bitmap(self.page_bitmap)

                region_bitmap = r.get_region_bitmap()

                if self._fits_page(page_information, region_bitmap):
                    self.page_bitmap = region_bitmap
                else:
                    region_info = r.get_region_info()
                    op = self._get_combination_operator(
                        page_information, region_info.get_combination_operator()
                    )
                    Bitmaps.blit(
                        region_bitmap,
                        self.page_bitmap,
                        region_info.get_x_location(),
                        region_info.get_y_location(),
                        op,
                    )

    def _fits_page(
        self, page_information: PageInformation, region_bitmap: Bitmap
    ) -> bool:
        """Whether a single region forms the complete page (see Issue 6)."""
        return (
            self._count_regions() == 1
            and page_information.get_default_pixel_value() == 0
            and page_information.get_width() == region_bitmap.get_width()
            and page_information.get_height() == region_bitmap.get_height()
        )

    def _create_striped_page(  # pragma: no cover
        self, page_information: PageInformation
    ) -> None:
        # Fixture-starved: reached only for a striped page with unknown height,
        # which the .jb2 corpus never contains (all striped fixtures carry a
        # known height and take the normal-page path). Hand-building a striped
        # stream needs real encoded stripe regions, so this stays uncovered.
        page_stripes = self._collect_page_stripes()

        self.page_bitmap = Bitmap(page_information.get_width(), self.final_height)

        start_line = 0
        for sd in page_stripes:
            if isinstance(sd, EndOfStripe):
                start_line = sd.get_line_number() + 1
            else:
                r: Region = sd
                region_info = r.get_region_info()
                op = self._get_combination_operator(
                    page_information, region_info.get_combination_operator()
                )
                Bitmaps.blit(
                    r.get_region_bitmap(),
                    self.page_bitmap,
                    region_info.get_x_location(),
                    start_line,
                    op,
                )

    def _collect_page_stripes(self) -> list[SegmentData]:  # pragma: no cover
        # Only invoked from _create_striped_page (the fixture-starved striped
        # path with unknown page height); see that method for why it is uncovered.
        page_stripes: list[SegmentData] = []
        for s in self.segments.values():
            # Page 79, 5).
            segment_type = s.get_segment_type()
            if segment_type in _REGION_SEGMENT_TYPES:
                r: Region = s.get_segment_data()
                page_stripes.append(r)
            elif segment_type == 50:  # End of stripe
                eos: EndOfStripe = s.get_segment_data()
                page_stripes.append(eos)
                self.final_height = eos.get_line_number() + 1

        return page_stripes

    def _count_regions(self) -> int:
        """Count the region segments.

        If there is only one region, the segment's bitmap is equal to the page
        bitmap and blitting is not necessary.
        """
        region_count = 0
        for s in self.segments.values():
            if s.get_segment_type() in _REGION_SEGMENT_TYPES:
                region_count += 1
        return region_count

    def _get_combination_operator(
        self, pi: PageInformation, new_operator: CombinationOperator
    ) -> CombinationOperator:
        """Decide which combination operator to use."""
        if pi.is_combination_operator_override_allowed():
            return new_operator
        return pi.get_combination_operator()

    def add(self, segment: SegmentHeader) -> None:
        """Add a :class:`SegmentHeader` into the page's segments map."""
        self.segments[segment.get_segment_nr()] = segment

    def _clear_segment_data(self) -> None:
        """Reset memory-critical segments to force on-demand decoding."""
        for key in self.segments:
            self.segments[key].clean_segment_data()

    def clear_page_data(self) -> None:
        """Reset the memory-critical parts of the page."""
        self.page_bitmap = None

    def get_height(self) -> int:
        """Return the final height of the page."""
        if self.final_height == 0:
            pi: PageInformation = (
                self.get_page_information_segment().get_segment_data()
            )
            if pi.get_height() == 0xFFFFFFFF:
                self.get_bitmap()
            else:
                self.final_height = pi.get_height()
        return self.final_height

    def get_width(self) -> int:
        if self.final_width == 0:
            pi: PageInformation = (
                self.get_page_information_segment().get_segment_data()
            )
            self.final_width = pi.get_width()
        return self.final_width

    def get_resolution_x(self) -> int:
        if self.resolution_x == 0:
            pi: PageInformation = (
                self.get_page_information_segment().get_segment_data()
            )
            self.resolution_x = pi.get_resolution_x()
        return self.resolution_x

    def get_resolution_y(self) -> int:
        if self.resolution_y == 0:
            pi: PageInformation = (
                self.get_page_information_segment().get_segment_data()
            )
            self.resolution_y = pi.get_resolution_y()
        return self.resolution_y

    def __str__(self) -> str:
        return f"{type(self).__name__} (Page number: {self.page_number})"
