from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName

from .fdf_annotation_text_markup import FDFAnnotationTextMarkup

_SUBTYPE: COSName = COSName.get_pdf_name("Subtype")


class FDFAnnotationSquiggly(FDFAnnotationTextMarkup):
    """FDF Squiggly annotation — ``/Subtype /Squiggly``.

    Mirrors ``org.apache.pdfbox.pdmodel.fdf.FDFAnnotationSquiggly``. Extends
    :class:`FDFAnnotationTextMarkup`, which carries the ``/QuadPoints`` helper.
    """

    SUBTYPE: str = "Squiggly"

    def __init__(self, annot: COSDictionary | None = None) -> None:
        super().__init__(annot)
        if annot is None or annot.get_dictionary_object(_SUBTYPE) is None:
            self.set_subtype(self.SUBTYPE)


__all__ = ["FDFAnnotationSquiggly"]
