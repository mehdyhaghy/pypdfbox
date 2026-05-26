from typing import Any

# NOTE: upstream types this map's values as SegmentHeader. SegmentHeader is
# ported in a later wave; until then the values are typed as ``Any``. When
# SegmentHeader lands, replace the ``Any`` annotations with the real type.


class JBIG2Globals:
    """Stores segments that aren't associated with a page.

    If the data is embedded in another format, for example PDF, these segments
    might be stored separately in the file. These segments are decoded on demand
    and all results are stored in the document object and can be retrieved from
    there.
    """

    def __init__(self) -> None:
        # This map contains all segments that are not associated with a page.
        # The key is the segment number.
        self.global_segments: dict[int, Any] = {}

    def get_segment(self, segment_nr: int) -> Any:
        return self.global_segments.get(segment_nr)

    def add_segment(self, segment_number: int, segment: Any) -> None:
        self.global_segments[segment_number] = segment
