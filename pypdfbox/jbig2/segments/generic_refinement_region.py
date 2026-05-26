"""Handles a JBIG2 Generic Refinement Region segment (§7.4.7).

Port of ``org.apache.pdfbox.jbig2.segments.GenericRefinementRegion``.

This class is responsible for segment-level concerns only: parsing the region
segment information and flags from the bitstream, resolving the reference
bitmap, and delegating pixel decoding to
:class:`~pypdfbox.jbig2.decoder.generic_refinement_region_decoding_procedure.GenericRefinementRegionDecodingProcedure`,
which implements the pure algorithm defined in §6.3.5.6.

Segment types (§7.4.7): the three generic refinement region segment types —
intermediate, immediate, and immediate lossless — share an identical data
encoding. They differ only in how the decoded bitmap is acted upon during page
image composition (§8.2).

Usage modes:

* **Header-driven (standalone segment):** initialise via :meth:`init`. The
  reference bitmap is resolved from referred-to segments or, if none are
  present, from the current page buffer (§7.4.7.4). Per Table 35,
  ``GRREFERENCEDX`` and ``GRREFERENCEDY`` are implicitly zero in this mode.
* **Parameter-driven:** call :meth:`set_parameters` to supply the shared
  ``ArithmeticDecoder``, ``CX``, reference bitmap, and offsets before calling
  :meth:`get_region_bitmap`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.jbig2.decoder.arithmetic.arithmetic_decoder import ArithmeticDecoder
from pypdfbox.jbig2.decoder.arithmetic.cx import CX
from pypdfbox.jbig2.decoder.generic_refinement_region_decoding_procedure import (
    GenericRefinementRegionDecodingProcedure,
)
from pypdfbox.jbig2.err.invalid_header_value_exception import (
    InvalidHeaderValueException,
)
from pypdfbox.jbig2.region import Region
from pypdfbox.jbig2.segments.region_segment_information import RegionSegmentInformation
from pypdfbox.jbig2.util.combination_operator import CombinationOperator

if TYPE_CHECKING:
    from pypdfbox.jbig2.bitmap import Bitmap
    from pypdfbox.jbig2.io.sub_input_stream import SubInputStream
    from pypdfbox.jbig2.segment_header import SegmentHeader


class GenericRefinementRegion(Region):
    """JBIG2 Generic Refinement Region segment (§7.4.7)."""

    def __init__(
        self,
        sub_input_stream: SubInputStream | None = None,
        segment_header: SegmentHeader | None = None,
    ) -> None:
        self.sub_input_stream = sub_input_stream
        self.segment_header = segment_header

        # Region segment information flags, 7.4.1
        self.region_info: RegionSegmentInformation | None = None
        if sub_input_stream is not None:
            self.region_info = RegionSegmentInformation(sub_input_stream)

        # Generic refinement region segment flags, 7.4.7.2
        self.is_tpgr_on = False
        self.template_id = 0

        # Generic refinement region segment AT flags, 7.4.7.3
        self.gr_at_x: list[int] | None = None
        self.gr_at_y: list[int] | None = None

        # Variables for decoding
        self.reference_bitmap: Bitmap | None = None
        self.reference_dx = 0
        self.reference_dy = 0

        self.arith_decoder: ArithmeticDecoder | None = None
        self.cx: CX | None = None

        self.page_bitmap: Bitmap | None = None

    def _parse_header(self) -> None:
        """Parse the flags described in the JBIG2 ISO standard.

        * 7.4.7.2 Generic refinement region segment flags
        * 7.4.7.3 Generic refinement region segment AT flags
        """
        self.region_info.parse_header()

        # Bit 2-7
        self.sub_input_stream.read_bits(6)  # Dirty read...

        # Bit 1
        if self.sub_input_stream.read_bit() == 1:
            self.is_tpgr_on = True

        # Bit 0
        self.template_id = self.sub_input_stream.read_bit()

        if self.template_id == 0:
            self._read_at_pixels()
        elif self.template_id == 1:
            pass

    def _read_at_pixels(self) -> None:
        # 7.4.7.3 Generic refinement region segment AT flags
        self.gr_at_x = [0, 0]
        self.gr_at_y = [0, 0]

        # Byte 0
        self.gr_at_x[0] = self.sub_input_stream.read_byte()
        # Byte 1
        self.gr_at_y[0] = self.sub_input_stream.read_byte()
        # Byte 2
        self.gr_at_x[1] = self.sub_input_stream.read_byte()
        # Byte 3
        self.gr_at_y[1] = self.sub_input_stream.read_byte()

    def get_region_bitmap(self) -> Bitmap:
        """Decode using a template and arithmetic coding, as described in 6.3.5.6.

        :raises OSError: if an underlying IO operation fails.
        :raises InvalidHeaderValueException: if a segment header value is invalid.
        :raises IntegerMaxValueException: if the maximum value limit of an integer
            is exceeded.
        """
        if self.reference_bitmap is None:
            # Get the reference bitmap, which is the base of refinement process
            self.reference_bitmap = self._get_gr_reference()

        if self.arith_decoder is None:
            self.arith_decoder = ArithmeticDecoder(self.sub_input_stream)

        if self.cx is None:
            self.cx = CX(8192, 1)

        return GenericRefinementRegionDecodingProcedure.decode(
            self.arith_decoder,
            self.cx,
            self.region_info.get_bitmap_width(),
            self.region_info.get_bitmap_height(),
            self.template_id,
            self.is_tpgr_on,
            self.reference_bitmap,
            self.reference_dx,
            self.reference_dy,
            self.gr_at_x,
            self.gr_at_y,
        )

    def set_page_bitmap(self, page_bitmap: Bitmap) -> None:
        """Call this to pass the page bitmap in case there is no reference bitmap."""
        self.page_bitmap = page_bitmap

    def _get_gr_reference(self) -> Bitmap:
        segments = self.segment_header.get_rt_segments()
        if segments is None:
            if (
                self.region_info.get_combination_operator()
                != CombinationOperator.REPLACE
            ):
                # 7.4.7.5 1) "If this segment does not refer to another region
                # segment then its external combination operator must be REPLACE"
                raise InvalidHeaderValueException(
                    "REPLACE combination operator expected"
                )
            # See page 79:
            # "The region segment is an immediate refinement region segment that
            #  refers to no other segments. In this case, the region segment is
            #  acting as a refinement of part of the page buffer."
            # 7.4.7.4 Reference bitmap selection: If this segment does not refer
            # to another region segment, set GRREFERENCE to be a bitmap
            # containing the current contents of the page buffer (see clause 8),
            # restricted to the area of the page buffer specified by this
            # segment's region segment information field.
            from pypdfbox.jbig2.image.bitmaps import Bitmaps

            roi = (
                self.region_info.get_x_location(),
                self.region_info.get_y_location(),
                self.region_info.get_bitmap_width(),
                self.region_info.get_bitmap_height(),
            )
            return Bitmaps.extract(roi, self.page_bitmap)
        region = segments[0].get_segment_data()

        return region.get_region_bitmap()

    def init(self, header: SegmentHeader, sis: SubInputStream) -> None:
        self.segment_header = header
        self.sub_input_stream = sis
        self.region_info = RegionSegmentInformation(self.sub_input_stream)
        self._parse_header()

    def set_parameters(
        self,
        cx: CX | None,
        arithmetic_decoder: ArithmeticDecoder | None,
        gr_template: int,
        region_width: int,
        region_height: int,
        gr_reference: Bitmap,
        gr_reference_dx: int,
        gr_reference_dy: int,
        is_tpgr_on: bool,
        gr_at_x: list[int] | None,
        gr_at_y: list[int] | None,
    ) -> None:
        if cx is not None:
            self.cx = cx

        if arithmetic_decoder is not None:
            self.arith_decoder = arithmetic_decoder

        self.template_id = gr_template

        self.region_info.set_bitmap_width(region_width)
        self.region_info.set_bitmap_height(region_height)

        self.reference_bitmap = gr_reference
        self.reference_dx = gr_reference_dx
        self.reference_dy = gr_reference_dy

        self.is_tpgr_on = is_tpgr_on

        self.gr_at_x = gr_at_x
        self.gr_at_y = gr_at_y

    def get_region_info(self) -> RegionSegmentInformation:
        return self.region_info
