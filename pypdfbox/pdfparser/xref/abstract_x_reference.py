from __future__ import annotations

from .x_reference_entry import XReferenceEntry
from .x_reference_type import XReferenceType


class AbstractXReference(XReferenceEntry):
    """Base class for concrete xref-stream entry types.

    Mirrors upstream
    ``org.apache.pdfbox.pdfparser.xref.AbstractXReference`` (an abstract
    class in Java implementing ``XReferenceEntry``). Holds the
    :class:`XReferenceType` tag and provides the column-1 default that
    all concrete entries share.
    """

    def __init__(self, type_: XReferenceType) -> None:
        self._type: XReferenceType = type_

    def get_type(self) -> XReferenceType:
        return self._type

    def get_first_column_value(self) -> int:
        """Column-1 value: the numeric tag of this entry's type.

        Mirrors upstream ``AbstractXReference.getFirstColumnValue``
        (Java line 60).
        """
        return self._type.get_numeric_value()
