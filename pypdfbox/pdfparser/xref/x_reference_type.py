from __future__ import annotations

from enum import Enum


class XReferenceType(Enum):
    """Type tag for an entry in a PDF crossreference stream.

    Mirrors upstream
    ``org.apache.pdfbox.pdfparser.xref.XReferenceType`` (Java enum).
    """

    FREE = 0
    NORMAL = 1
    OBJECT_STREAM_ENTRY = 2

    def get_numeric_value(self) -> int:
        """Return the integer encoding written to the xref stream.

        Mirrors upstream ``XReferenceType.getNumericValue`` (Java line 49).
        """
        return self.value
