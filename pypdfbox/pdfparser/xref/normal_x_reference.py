from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos.cos_name import COSName

from .abstract_x_reference import AbstractXReference
from .x_reference_type import XReferenceType

if TYPE_CHECKING:
    from pypdfbox.cos.cos_base import COSBase
    from pypdfbox.cos.cos_object_key import COSObjectKey


class NormalXReference(AbstractXReference):
    """A NORMAL entry in a PDF crossreference stream.

    Mirrors upstream
    ``org.apache.pdfbox.pdfparser.xref.NormalXReference``. Tracks the
    byte offset of the referenced object plus whether that object is
    itself an object stream (``/Type /ObjStm``).
    """

    def __init__(
        self,
        byte_offset: int,
        key: COSObjectKey,
        obj: COSBase,
    ) -> None:
        super().__init__(XReferenceType.NORMAL)
        self._byte_offset: int = byte_offset
        self._key: COSObjectKey = key
        self._object: COSBase = obj
        self._object_stream: bool = self._is_object_stream(obj)

    @staticmethod
    def _is_object_stream(obj: COSBase) -> bool:
        from pypdfbox.cos.cos_object import COSObject  # noqa: PLC0415
        from pypdfbox.cos.cos_stream import COSStream  # noqa: PLC0415

        base = obj.get_object() if isinstance(obj, COSObject) else obj
        if isinstance(base, COSStream):
            # ``COSName.OBJ_STM`` is upstream's constant for ``/ObjStm``;
            # not every pypdfbox build defines it as a class attribute, so
            # fall back to constructing the name on demand.
            obj_stm = getattr(COSName, "OBJ_STM", None) or COSName.get_pdf_name("ObjStm")
            return obj_stm == base.get_cos_name(COSName.TYPE)
        return False

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    def get_byte_offset(self) -> int:
        """Byte offset of the referenced object in the PDF file.

        Mirrors upstream ``getByteOffset`` (Java line 69).
        """
        return self._byte_offset

    def get_referenced_key(self) -> COSObjectKey:
        return self._key

    def get_object(self) -> COSBase:
        """Return the wrapped ``COSBase``.

        Mirrors upstream ``getObject`` (Java line 90).
        """
        return self._object

    def is_object_stream(self) -> bool:
        """``True`` if the referenced object is an object stream.

        Mirrors upstream ``isObjectStream`` (Java line 100).
        """
        return self._object_stream

    def get_second_column_value(self) -> int:
        """Column-2 value: byte offset of the object.

        Mirrors upstream ``NormalXReference.getSecondColumnValue``
        (Java line 112).
        """
        return self.get_byte_offset()

    def get_third_column_value(self) -> int:
        """Column-3 value: generation number of the object.

        Mirrors upstream ``NormalXReference.getThirdColumnValue``
        (Java line 124).
        """
        return self.get_referenced_key().get_generation()

    def __repr__(self) -> str:
        head = "ObjectStreamParent{" if self.is_object_stream() else "NormalReference{"
        return (
            head
            + f" key={self._key}, type={self.get_type().get_numeric_value()}, "
            f"byteOffset={self._byte_offset} }}"
        )

    __str__ = __repr__

    def to_string(self) -> str:
        """Java-name parity alias for ``__str__``.

        Mirrors upstream ``NormalXReference.toString`` (Java line 135).
        """
        return str(self)
