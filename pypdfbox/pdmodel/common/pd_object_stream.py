from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos import COSName, COSStream

from .pd_stream import PDStream

if TYPE_CHECKING:
    from pypdfbox.pdmodel.pd_document import PDDocument


_TYPE: COSName = COSName.get_pdf_name("Type")
_OBJ_STM: COSName = COSName.get_pdf_name("ObjStm")
_N: COSName = COSName.get_pdf_name("N")
_FIRST: COSName = COSName.get_pdf_name("First")
_EXTENDS: COSName = COSName.get_pdf_name("Extends")


class PDObjectStream(PDStream):
    """PD-level wrapper for an object stream (``/Type /ObjStm``).

    Mirrors ``org.apache.pdfbox.pdmodel.common.PDObjectStream`` (Java
    lines 32-131). Object streams (PDF 32000-1 §7.5.7) carry compressed
    PDF indirect objects inline; this class exposes the entries that
    describe the stream's layout (``/N`` object count, ``/First`` byte
    offset, ``/Extends`` chain) on top of the standard :class:`PDStream`
    surface.
    """

    def __init__(self, str_: COSStream) -> None:
        """Wrap an existing ``COSStream``. Mirrors upstream constructor
        (Java line 40)."""
        super().__init__(str_)

    @staticmethod
    def create_stream(document: PDDocument) -> PDObjectStream:
        """Create a fresh object stream attached to ``document``.

        Mirrors upstream ``createStream(PDDocument)`` (Java line 51).
        """
        cos_stream = document.get_document().create_cos_stream()
        strm = PDObjectStream(cos_stream)
        strm.get_cos_object().set_item(_TYPE, _OBJ_STM)
        return strm

    # ---------- /Type ----------

    def get_type(self) -> str | None:
        """Return the ``/Type`` value (``"ObjStm"``).

        Mirrors upstream ``getType()`` (Java line 64).
        """
        return self.get_cos_object().get_name_as_string(_TYPE)

    # ---------- /N number of objects ----------

    def get_number_of_objects(self) -> int:
        """Return the compressed-object count (``/N``).

        Mirrors upstream ``getNumberOfObjects()`` (Java line 74).
        """
        return self.get_cos_object().get_int(_N, 0)

    def set_number_of_objects(self, n: int) -> None:
        """Set the compressed-object count (``/N``).

        Mirrors upstream ``setNumberOfObjects(int)`` (Java line 84).
        """
        self.get_cos_object().set_int(_N, n)

    # ---------- /First first byte offset ----------

    def get_first_byte_offset(self) -> int:
        """Return the byte offset (in the decoded stream) of the first
        compressed object (``/First``).

        Mirrors upstream ``getFirstByteOffset()`` (Java line 94).
        """
        return self.get_cos_object().get_int(_FIRST, 0)

    def set_first_byte_offset(self, n: int) -> None:
        """Set the byte offset of the first compressed object (``/First``).

        Mirrors upstream ``setFirstByteOffset(int)`` (Java line 104).
        """
        self.get_cos_object().set_int(_FIRST, n)

    # ---------- /Extends chain ----------

    def get_extends(self) -> PDObjectStream | None:
        """Return the parent object stream referenced via ``/Extends``.

        Mirrors upstream ``getExtends()`` (Java line 115).
        """
        stream = self.get_cos_object().get_cos_stream(_EXTENDS)
        if isinstance(stream, COSStream):
            return PDObjectStream(stream)
        return None

    def set_extends(self, stream: PDObjectStream | None) -> None:
        """Set the parent object stream (``/Extends``).

        Mirrors upstream ``setExtends(PDObjectStream)`` (Java line 127).
        """
        if stream is None:
            self.get_cos_object().remove_item(_EXTENDS)
            return
        self.get_cos_object().set_item(_EXTENDS, stream.get_cos_object())


__all__ = ["PDObjectStream"]
