from __future__ import annotations

from typing import TYPE_CHECKING

from .abstract_x_reference import AbstractXReference
from .x_reference_type import XReferenceType

if TYPE_CHECKING:
    from pypdfbox.cos.cos_base import COSBase
    from pypdfbox.cos.cos_object_key import COSObjectKey


class ObjectStreamXReference(AbstractXReference):
    """An OBJECT_STREAM_ENTRY xref entry — a compressed object inside an
    object stream.

    Mirrors upstream
    ``org.apache.pdfbox.pdfparser.xref.ObjectStreamXReference``.
    """

    def __init__(
        self,
        object_stream_index: int,
        key: COSObjectKey,
        obj: COSBase,
        parent_key: COSObjectKey,
    ) -> None:
        super().__init__(XReferenceType.OBJECT_STREAM_ENTRY)
        self._object_stream_index: int = object_stream_index
        self._key: COSObjectKey = key
        self._object: COSBase = obj
        self._parent_key: COSObjectKey = parent_key

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    def get_object_stream_index(self) -> int:
        """Position of this object within its containing object stream.

        Mirrors upstream ``getObjectStreamIndex`` (Java line 61).
        """
        return self._object_stream_index

    def get_referenced_key(self) -> COSObjectKey:
        return self._key

    def get_object(self) -> COSBase:
        """Return the wrapped ``COSBase``.

        Mirrors upstream ``getObject`` (Java line 82).
        """
        return self._object

    def get_parent_key(self) -> COSObjectKey:
        """``COSObjectKey`` of the containing object stream.

        Mirrors upstream ``getParentKey`` (Java line 92).
        """
        return self._parent_key

    def get_second_column_value(self) -> int:
        """Column-2 value: parent object stream's object number.

        Mirrors upstream
        ``ObjectStreamXReference.getSecondColumnValue`` (Java line 105).
        """
        return self.get_parent_key().get_number()

    def get_third_column_value(self) -> int:
        """Column-3 value: index within the containing object stream.

        Mirrors upstream
        ``ObjectStreamXReference.getThirdColumnValue`` (Java line 117).
        """
        return self.get_object_stream_index()

    def __repr__(self) -> str:
        return (
            "ObjectStreamEntry{"
            f" key={self._key}, type={self.get_type().get_numeric_value()}, "
            f"objectStreamIndex={self._object_stream_index}, "
            f"parent={self._parent_key} }}"
        )

    __str__ = __repr__

    def to_string(self) -> str:
        """Java-name parity alias for ``__str__``.

        Mirrors upstream ``ObjectStreamXReference.toString`` (Java line
        128).
        """
        return str(self)
