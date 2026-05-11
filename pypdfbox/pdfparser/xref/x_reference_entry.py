from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pypdfbox.cos.cos_object_key import COSObjectKey

    from .x_reference_type import XReferenceType


class XReferenceEntry(ABC):
    """A single entry in a PDF crossreference stream.

    Mirrors upstream
    ``org.apache.pdfbox.pdfparser.xref.XReferenceEntry`` (an interface in
    Java that extends ``Comparable<XReferenceEntry>``). Concrete entries
    are :class:`FreeXReference`, :class:`NormalXReference` and
    :class:`ObjectStreamXReference`.
    """

    @abstractmethod
    def get_type(self) -> XReferenceType:
        """Return the :class:`XReferenceType` of this entry.

        Mirrors upstream ``getType`` (Java line 36).
        """

    @abstractmethod
    def get_referenced_key(self) -> COSObjectKey:
        """Return the :class:`COSObjectKey` this entry describes.

        Mirrors upstream ``getReferencedKey`` (Java line 43).
        """

    @abstractmethod
    def get_first_column_value(self) -> int:
        """Numeric encoding of :meth:`get_type` written to column 1.

        Mirrors upstream ``getFirstColumnValue`` (Java line 51).
        """

    @abstractmethod
    def get_second_column_value(self) -> int:
        """Column-2 value (meaning depends on type).

        Mirrors upstream ``getSecondColumnValue`` (Java line 59).
        """

    @abstractmethod
    def get_third_column_value(self) -> int:
        """Column-3 value (meaning depends on type).

        Mirrors upstream ``getThirdColumnValue`` (Java line 67).
        """

    def compare_to(self, other: XReferenceEntry | None) -> int:
        """Ordering on the referenced key.

        Mirrors upstream ``AbstractXReference.compareTo`` (Java line 74).
        Provided here so the interface is total: implementations get a
        default ordering for free.
        """
        own_key = self.get_referenced_key()
        if own_key is None:
            return -1
        if other is None or other.get_referenced_key() is None:
            return 1
        return own_key.compare_to(other.get_referenced_key())

    # Python comparison sugar so callers can sort lists with ``sort()``.
    def __lt__(self, other: object) -> bool:
        if not isinstance(other, XReferenceEntry):
            return NotImplemented
        return self.compare_to(other) < 0

    def __le__(self, other: object) -> bool:
        if not isinstance(other, XReferenceEntry):
            return NotImplemented
        return self.compare_to(other) <= 0

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, XReferenceEntry):
            return NotImplemented
        return self.compare_to(other) > 0

    def __ge__(self, other: object) -> bool:
        if not isinstance(other, XReferenceEntry):
            return NotImplemented
        return self.compare_to(other) >= 0
