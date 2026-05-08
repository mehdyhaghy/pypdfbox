from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName

from .fdf_annotation import FDFAnnotation

_SUBTYPE: COSName = COSName.get_pdf_name("Subtype")


class FDFAnnotationFileAttachment(FDFAnnotation):
    """FDF file attachment annotation - ``/Subtype /FileAttachment``.

    Mirrors ``org.apache.pdfbox.pdmodel.fdf.FDFAnnotationFileAttachment``.
    """

    SUBTYPE: str = "FileAttachment"

    def __init__(self, annot: COSDictionary | None = None) -> None:
        super().__init__(annot)
        if annot is None or annot.get_dictionary_object(_SUBTYPE) is None:
            self.set_subtype(self.SUBTYPE)


__all__ = ["FDFAnnotationFileAttachment"]
