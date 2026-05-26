from __future__ import annotations

import weakref
from typing import TYPE_CHECKING, Any

from pypdfbox.jbig2.io.sub_input_stream import SubInputStream
from pypdfbox.jbig2.segment_data import SegmentData

if TYPE_CHECKING:
    from pypdfbox.jbig2.io.image_input_stream import ImageInputStream

# Organisation type constants. Upstream these live on JBIG2Document
# (``JBIG2Document.RANDOM`` / ``JBIG2Document.SEQUENTIAL``). The values are
# mirrored here so the header parser can stand alone. RANDOM = 0, SEQUENTIAL = 1.
RANDOM = 0
SEQUENTIAL = 1


def _build_segment_type_map() -> dict[int, type[SegmentData]]:
    """Build the segment-type -> SegmentData subclass dispatch (7.3).

    The concrete segment classes are imported lazily so that importing
    :mod:`segment_header` does not eagerly pull in the heavy region/dictionary
    decoders (and to avoid any import cycles). Mirrors the static
    ``SEGMENT_TYPE_MAP`` block in upstream ``SegmentHeader``.
    """
    from pypdfbox.jbig2.segments.end_of_stripe import EndOfStripe
    from pypdfbox.jbig2.segments.generic_refinement_region import (
        GenericRefinementRegion,
    )
    from pypdfbox.jbig2.segments.generic_region import GenericRegion
    from pypdfbox.jbig2.segments.halftone_region import HalftoneRegion
    from pypdfbox.jbig2.segments.page_information import PageInformation
    from pypdfbox.jbig2.segments.pattern_dictionary import PatternDictionary
    from pypdfbox.jbig2.segments.profiles import Profiles
    from pypdfbox.jbig2.segments.symbol_dictionary import SymbolDictionary
    from pypdfbox.jbig2.segments.table import Table
    from pypdfbox.jbig2.segments.text_region import TextRegion

    return {
        0: SymbolDictionary,
        4: TextRegion,
        6: TextRegion,
        7: TextRegion,
        16: PatternDictionary,
        20: HalftoneRegion,
        22: HalftoneRegion,
        23: HalftoneRegion,
        36: GenericRegion,
        38: GenericRegion,
        39: GenericRegion,
        40: GenericRefinementRegion,
        42: GenericRefinementRegion,
        43: GenericRefinementRegion,
        48: PageInformation,
        50: EndOfStripe,
        52: Profiles,
        53: Table,
    }


# Lazily-populated dispatch cache. Populated on first ``get_segment_data()``.
SEGMENT_TYPE_MAP: dict[int, type[SegmentData]] = {}


class SegmentHeader:
    """The basic class for all JBIG2 segments.

    Mirrors ``org.apache.pdfbox.jbig2.SegmentHeader``. Parses a segment header:
    number, flags, type, referred-to segments, page association and data length.
    """

    def __init__(
        self,
        document: Any,
        sis: SubInputStream,
        offset: int,
        organisation_type: int,
    ) -> None:
        self.sub_input_stream = sis

        self.segment_nr = 0
        self.segment_type = 0
        self.retain_flag = 0
        self.page_association = 0
        self.page_association_field_size = 0
        self.rt_segments: list[SegmentHeader | None] | None = None
        self.segment_header_length = 0
        self.segment_data_length = 0
        self.segment_data_start_offset = 0

        self._segment_data: weakref.ref[SegmentData] | None = None

        self._parse(document, sis, offset, organisation_type)

    def _parse(
        self,
        document: Any,
        sub_input_stream: ImageInputStream,
        offset: int,
        organisation_type: int,
    ) -> None:
        """Parse the segment header.

        :param offset: The offset where the segment header starts.
        """
        sub_input_stream.seek(offset)

        # 7.2.2 Segment number
        self._read_segment_number(sub_input_stream)

        # 7.2.3 Segment header flags
        self._read_segment_header_flag(sub_input_stream)

        # 7.2.4 Amount of referred-to segments
        count_of_rts = self._read_amount_of_referred_to_segments(sub_input_stream)

        # 7.2.5 Referred-to segments numbers
        rts_numbers = self._read_referred_to_segments_numbers(
            sub_input_stream, count_of_rts
        )

        # 7.2.6 Segment page association (Checks how big the page association
        # field is.)
        self._read_segment_page_association(
            document, sub_input_stream, count_of_rts, rts_numbers
        )

        # 7.2.7 Segment data length (Contains the length of the data part (in
        # bytes).)
        self._read_segment_data_length(sub_input_stream)

        self._read_data_start_offset(sub_input_stream, organisation_type)
        self._read_segment_header_length(sub_input_stream, offset)

    def _read_segment_number(self, sub_input_stream: ImageInputStream) -> None:
        # 7.2.2 Segment number
        self.segment_nr = int(sub_input_stream.read_bits(32) & 0xFFFFFFFF)

    def _read_segment_header_flag(self, sub_input_stream: ImageInputStream) -> None:
        # 7.2.3 Segment header flags

        # Bit 7: Retain Flag, if 1, this segment is flagged as retained
        self.retain_flag = sub_input_stream.read_bit()

        # Bit 6: Size of the page association field. One byte if 0, four bytes
        # if 1
        self.page_association_field_size = sub_input_stream.read_bit()

        # Bit 5-0: Contains the values (between 0 and 62 with gaps) for segment
        # types, specified in 7.3
        self.segment_type = int(sub_input_stream.read_bits(6) & 0xFF)

    def _read_amount_of_referred_to_segments(
        self, sub_input_stream: ImageInputStream
    ) -> int:
        # 7.2.4 Amount of referred-to segments
        count_of_rts = int(sub_input_stream.read_bits(3) & 0xF)

        if count_of_rts <= 4:
            # short format
            for _i in range(5):
                sub_input_stream.read_bit()
        else:
            # long format
            count_of_rts = int(sub_input_stream.read_bits(29) & 0xFFFFFFFF)

            array_length = (count_of_rts + 8) >> 3
            array_length <<= 3

            for _i in range(array_length):
                sub_input_stream.read_bit()

        return count_of_rts

    def _read_referred_to_segments_numbers(
        self, sub_input_stream: ImageInputStream, count_of_rts: int
    ) -> list[int]:
        """7.2.5 Referred-to segments numbers.

        Gathers all segment numbers of referred-to segments. The segments
        themselves are stored in the :attr:`rt_segments` list.

        :return: A list with the segment number of all referred-to segments.
        """
        rts_numbers = [0] * count_of_rts

        if count_of_rts > 0:
            rts_size = 1
            if self.segment_nr > 256:
                rts_size = 2
                if self.segment_nr > 65536:
                    rts_size = 4

            self.rt_segments = [None] * count_of_rts

            for i in range(count_of_rts):
                rts_numbers[i] = int(
                    sub_input_stream.read_bits(rts_size << 3) & 0xFFFFFFFF
                )

        return rts_numbers

    def _read_segment_page_association(
        self,
        document: Any,
        sub_input_stream: ImageInputStream,
        count_of_rts: int,
        rts_numbers: list[int],
    ) -> None:
        # 7.2.6 Segment page association
        if self.page_association_field_size == 0:
            # Short format
            self.page_association = int(sub_input_stream.read_bits(8) & 0xFF)
        else:
            # Long format
            self.page_association = int(sub_input_stream.read_bits(32) & 0xFFFFFFFF)

        if count_of_rts > 0:
            # document may be None when parsing a header in isolation (no
            # JBIG2Document context). In that case the referred-to SegmentHeader
            # objects cannot be resolved and stay None; their numbers were still
            # read above to keep the bit position correct.
            page = (
                document.get_page(self.page_association)
                if document is not None
                else None
            )
            for i in range(count_of_rts):
                if document is None:
                    self.rt_segments[i] = None
                elif page is not None:
                    self.rt_segments[i] = page.get_segment(rts_numbers[i])
                else:
                    self.rt_segments[i] = document.get_global_segment(rts_numbers[i])

    def _read_segment_data_length(self, sub_input_stream: ImageInputStream) -> None:
        """7.2.7 Segment data length.

        Contains the length of the data part in bytes.
        """
        self.segment_data_length = sub_input_stream.read_bits(32) & 0xFFFFFFFF

    def _read_data_start_offset(
        self, sub_input_stream: ImageInputStream, organisation_type: int
    ) -> None:
        """Set the offset only if organisation type is SEQUENTIAL.

        If random, data starts after segment headers and can be determined when
        all segment headers are parsed and allocated.
        """
        if organisation_type == SEQUENTIAL:
            self.segment_data_start_offset = sub_input_stream.get_stream_position()

    def _read_segment_header_length(
        self, sub_input_stream: ImageInputStream, offset: int
    ) -> None:
        self.segment_header_length = sub_input_stream.get_stream_position() - offset

    def get_segment_nr(self) -> int:
        return self.segment_nr

    def get_segment_type(self) -> int:
        return self.segment_type

    def get_segment_header_length(self) -> int:
        return self.segment_header_length

    def get_segment_data_length(self) -> int:
        return self.segment_data_length

    def get_segment_data_start_offset(self) -> int:
        return self.segment_data_start_offset

    def set_segment_data_start_offset(self, segment_data_start_offset: int) -> None:
        self.segment_data_start_offset = segment_data_start_offset

    def get_rt_segments(self) -> list[SegmentHeader | None] | None:
        return self.rt_segments

    def get_page_association(self) -> int:
        return self.page_association

    def get_retain_flag(self) -> int:
        return self.retain_flag

    def get_data_input_stream(self) -> SubInputStream:
        """Create and return a new :class:`SubInputStream` for the data part.

        It is a clipped view of the source input stream.
        """
        return SubInputStream(
            self.sub_input_stream,
            self.segment_data_start_offset,
            self.segment_data_length,
        )

    def get_segment_data(self) -> SegmentData:
        """Retrieve the segment's data part.

        :return: Retrieved :class:`SegmentData` instance.
        """
        segment_data_part = None

        if self._segment_data is not None:
            segment_data_part = self._segment_data()

        if segment_data_part is None:
            if not SEGMENT_TYPE_MAP:
                SEGMENT_TYPE_MAP.update(_build_segment_type_map())
            segment_class = SEGMENT_TYPE_MAP.get(self.segment_type)
            if segment_class is None:
                raise ValueError(f"No segment class for type {self.segment_type}")
            try:
                segment_data_part = segment_class()
                segment_data_part.init(self, self.get_data_input_stream())
                self._segment_data = weakref.ref(segment_data_part)
            except Exception as e:
                raise RuntimeError(
                    f"Can't instantiate segment class {segment_class.__name__} "
                    f"because of {type(e).__name__}: {e}"
                ) from e

        return segment_data_part

    def clean_segment_data(self) -> None:
        if self._segment_data is not None:
            self._segment_data = None

    def __str__(self) -> str:
        if self.rt_segments is not None:
            referred = "".join(
                f"{s.segment_nr} " for s in self.rt_segments if s is not None
            )
        else:
            referred = "none"

        return (
            f"\n#SegmentNr: {self.segment_nr}"
            f"\n SegmentType: {self.segment_type}"
            f"\n PageAssociation: {self.page_association}"
            f"\n Referred-to segments: {referred}"
            "\n"
        )
