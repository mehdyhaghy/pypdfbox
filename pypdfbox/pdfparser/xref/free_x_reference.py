from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from pypdfbox.cos.cos_object_key import COSObjectKey

from .abstract_x_reference import AbstractXReference
from .x_reference_type import XReferenceType

if TYPE_CHECKING:
    pass


class FreeXReference(AbstractXReference):
    """A FREE entry in a PDF crossreference stream.

    Mirrors upstream
    ``org.apache.pdfbox.pdfparser.xref.FreeXReference``.
    """

    # Sentinel entry: ``0 65535 R`` with no successor. Set after the class
    # body so the constructor is fully bound.
    NULL_ENTRY: ClassVar[FreeXReference]

    def __init__(self, key: COSObjectKey, next_free_object: int) -> None:
        super().__init__(XReferenceType.FREE)
        self._key: COSObjectKey = key
        self._next_free_object: int = next_free_object

    def get_referenced_key(self) -> COSObjectKey:
        return self._key

    def get_second_column_value(self) -> int:
        """Column-2 value: object number of the next free object.

        Mirrors upstream ``FreeXReference.getSecondColumnValue``
        (Java line 66).
        """
        return self._next_free_object

    def get_third_column_value(self) -> int:
        """Column-3 value: generation of the next free object.

        Mirrors upstream ``FreeXReference.getThirdColumnValue``
        (Java line 78).
        """
        return self.get_referenced_key().get_generation()

    def __repr__(self) -> str:
        return (
            "FreeReference{"
            f"key={self._key}, nextFreeObject={self._next_free_object}, "
            f"type={self.get_type().get_numeric_value()} }}"
        )

    __str__ = __repr__

    def to_string(self) -> str:
        """Java-name parity alias for ``__str__``.

        Mirrors upstream ``FreeXReference.toString`` (Java line 89).
        """
        return str(self)


FreeXReference.NULL_ENTRY = FreeXReference(COSObjectKey(0, 65535), 0)
