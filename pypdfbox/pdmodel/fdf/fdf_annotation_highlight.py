from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName

from .fdf_annotation_text_markup import FDFAnnotationTextMarkup

_SUBTYPE: COSName = COSName.get_pdf_name("Subtype")


class FDFAnnotationHighlight(FDFAnnotationTextMarkup):
    """FDF Highlight annotation — ``/Subtype /Highlight``.

    Mirrors ``org.apache.pdfbox.pdmodel.fdf.FDFAnnotationHighlight``. Extends
    :class:`FDFAnnotationTextMarkup`, which carries the ``/QuadPoints`` helper.
    """

    SUBTYPE: str = "Highlight"

    def __init__(self, annot: COSDictionary | None = None) -> None:
        super().__init__(annot)
        if annot is None or annot.get_dictionary_object(_SUBTYPE) is None:
            self.set_subtype(self.SUBTYPE)


__all__ = ["FDFAnnotationHighlight"]
