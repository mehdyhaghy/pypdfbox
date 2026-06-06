from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.jbig2.io.sub_input_stream import SubInputStream
from pypdfbox.jbig2.jbig2_globals import JBIG2Globals
from pypdfbox.jbig2.jbig2_page import JBIG2Page
from pypdfbox.jbig2.segment_header import SegmentHeader

if TYPE_CHECKING:
    from pypdfbox.jbig2.io.image_input_stream import ImageInputStream

# A practical stand-in for Java's ``Long.MAX_VALUE`` used to wrap the whole
# source stream in a SubInputStream window.
_LONG_MAX_VALUE = 0x7FFFFFFFFFFFFFFF


class JBIG2Document:
    """Represents the document structure with its pages and global segments.

    Mirrors ``org.apache.pdfbox.jbig2.JBIG2Document``. Handles both the embedded
    organisation (e.g. inside a PDF — bare segments, no file header, globals
    supplied separately) and the standalone organisation (a ``.jb2`` file that
    starts with the JBIG2 file header).
    """

    # ID string in file header, see ISO/IEC 14492:2001, D.4.1
    FILE_HEADER_ID = (0x97, 0x4A, 0x42, 0x32, 0x0D, 0x0A, 0x1A, 0x0A)

    # File organisation types, D.4.2 - File header bit 0.
    RANDOM = 0
    SEQUENTIAL = 1

    def __init__(
        self, input_stream: ImageInputStream, globals: JBIG2Globals | None = None
    ) -> None:
        if input_stream is None:
            raise ValueError("imageInputStream must not be null")

        # This map contains all pages of this document. The key is the number of
        # the page. A dict preserves insertion order; the page-number keys are
        # iterated in ascending order via sorted() where upstream relies on the
        # TreeMap ordering.
        self.pages: dict[int, JBIG2Page] = {}

        # The length of the file header if it exists.
        self.file_header_length = 9

        # According to D.4.2 - File header bit 0. 1 == sequential, 0 == random.
        self.organisation_type = self.SEQUENTIAL

        # According to D.4.2 - Bit 1. True if the amount of pages is unknown.
        self.amount_of_pages_unknown = True

        # According to D.4.3 - Number of pages field (only present if
        # amount_of_pages_unknown is False).
        self.amount_of_pages = 0

        # Defines whether the extended template is used.
        self.gb_use_ext_template = False

        # The source data stream wrapped into a SubInputStream.
        self.sub_input_stream = SubInputStream(input_stream, 0, _LONG_MAX_VALUE)

        # Holds segments that aren't associated with a page.
        self.global_segments: JBIG2Globals | None = globals

        self._map_stream()

    def get_global_segment(self, segment_nr: int) -> SegmentHeader | None:
        """Retrieve the global (page-less) segment with the given number."""
        if self.global_segments is not None:
            return self.global_segments.get_segment(segment_nr)
        # Unreachable in practice: _map_stream (run from __init__) always
        # assigns a JBIG2Globals instance, so global_segments is never None
        # after construction. Kept to mirror upstream's defensive null guard.
        return None  # pragma: no cover

    def get_page(self, page_number: int) -> JBIG2Page | None:
        """Retrieve a :class:`JBIG2Page` specified by the given page number."""
        return self.pages.get(page_number)

    def get_amount_of_pages(self) -> int:
        """Return the amount of pages in this document.

        If the pages are striped, the document is completely parsed and the
        amount of pages is gathered.
        """
        if self.amount_of_pages_unknown or self.amount_of_pages == 0:
            if not self.pages:
                self._map_stream()
            return len(self.pages)
        return self.amount_of_pages

    def _map_stream(self) -> None:
        """Map the stream and store all segments."""
        segments: list[SegmentHeader] = []

        offset = 0
        segment_type = 0

        # Rewind to the window start before scanning. Upstream's first
        # ``mapStream()`` always runs with the SubInputStream freshly at
        # position 0, so ``isFileHeaderPresent()`` (which marks/reads/resets
        # *from the current position*) sees the header. ``getAmountOfPages``
        # may invoke ``mapStream()`` a SECOND time when the first pass produced
        # no pages (a degenerate file-header-only / zero-segment globals
        # stream); by then the prior pass left the sub stream seeked to the
        # post-header offset, so without this rewind ``isFileHeaderPresent()``
        # would read past EOF (-1), skip header parsing, and run a phantom
        # segment parse off the end (EOFError). Seeking to 0 makes the re-map
        # deterministically reproduce the first pass — the well-defined
        # upstream outcome for such a stream (no pages) — instead of crashing.
        self.sub_input_stream.seek(0)

        # Parse the file header if there is one.
        if self._is_file_header_present():
            self._parse_file_header()
            offset += self.file_header_length

        if self.global_segments is None:
            self.global_segments = JBIG2Globals()

        # If organisation type is random-access, walk through the segment
        # headers until the EOF segment appears (segment type 51).
        while segment_type != 51 and not self._reached_end_of_stream(offset):
            segment = SegmentHeader(
                self, self.sub_input_stream, offset, self.organisation_type
            )

            associated_page = segment.get_page_association()
            segment_type = segment.get_segment_type()

            if associated_page != 0:
                page = self.get_page(associated_page)
                if page is None:
                    page = JBIG2Page(self, associated_page)
                    self.pages[associated_page] = page
                page.add(segment)
            else:
                self.global_segments.add_segment(segment.get_segment_nr(), segment)
            segments.append(segment)

            offset = self.sub_input_stream.get_stream_position()

            # Sequential organisation skips data part and sets the offset.
            if self.organisation_type == self.SEQUENTIAL:
                offset += segment.get_segment_data_length()

        # PDFBOX-6147: abort if first page isn't 1, however a purely empty
        # document is valid when calling "new JBIG2Document(globals)".
        if self.pages and self.pages.get(1) is None:
            raise OSError("Page 1 missing")

        # Random organisation: segment headers are finished. Data part starts
        # and the offset can be set.
        self._determine_random_data_offsets(segments, offset)

    def _is_file_header_present(self) -> bool:
        input_stream = self.sub_input_stream
        input_stream.mark()

        for magic_byte in self.FILE_HEADER_ID:
            if magic_byte != input_stream.read():
                input_stream.reset()
                return False

        input_stream.reset()
        return True

    def _determine_random_data_offsets(
        self, segments: list[SegmentHeader], offset: int
    ) -> None:
        """Determine the start of the data parts and set the offset."""
        if self.organisation_type == self.RANDOM:
            for s in segments:
                s.set_segment_data_start_offset(offset)
                offset += s.get_segment_data_length()

    def _parse_file_header(self) -> None:
        """Read the file header and set the organisation/length variables."""
        self.sub_input_stream.seek(0)

        # D.4.1 - ID string, read will be skipped.
        self.sub_input_stream.skip_bytes(8)

        # D.4.2 Header flag (1 byte).

        # Bit 3-7 are reserved and must be 0.
        self.sub_input_stream.read_bits(5)

        # Bit 2 - Indicates if extended templates are used.
        if self.sub_input_stream.read_bit() == 1:
            self.gb_use_ext_template = True

        # Bit 1 - Indicates if the amount of pages is unknown.
        if self.sub_input_stream.read_bit() != 1:
            self.amount_of_pages_unknown = False

        # Bit 0 - Indicates the file organisation type.
        self.organisation_type = self.sub_input_stream.read_bit()

        # D.4.3 Number of pages (only present if the amount of pages is known).
        if not self.amount_of_pages_unknown:
            self.amount_of_pages = int(
                self.sub_input_stream.read_unsigned_int() & 0xFFFFFFFF
            )
            self.file_header_length = 13

    def _reached_end_of_stream(self, offset: int) -> bool:
        """Check whether the stream is at its end (reads 32 bits to test)."""
        try:
            self.sub_input_stream.seek(offset)
            self.sub_input_stream.read_bits(32)
            return False
        except EOFError:
            return True
        except IndexError:  # pragma: no cover
            # Defensive: read_bits past the stream window always surfaces as
            # EOFError (ImageInputStream.read_fully raises EOFError, never
            # IndexError, on this path). Kept as a belt-and-braces guard
            # alongside the EOFError branch.
            return True

    def get_global_segments(self) -> JBIG2Globals | None:
        return self.global_segments

    def is_amount_of_pages_unknown(self) -> bool:
        return self.amount_of_pages_unknown

    def is_gb_use_ext_template(self) -> bool:
        return self.gb_use_ext_template
