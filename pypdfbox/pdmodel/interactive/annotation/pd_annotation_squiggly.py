from __future__ import annotations

from pypdfbox.cos import COSDictionary

from .pd_annotation_text_markup import PDAnnotationTextMarkup


class PDAnnotationSquiggly(PDAnnotationTextMarkup):
    """``/Subtype /Squiggly`` text markup annotation. Mirrors
    ``org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationSquiggly``.
    """

    SUB_TYPE: str = "Squiggly"

    def __init__(self, annotation_dict: COSDictionary | None = None) -> None:
        super().__init__(annotation_dict)
        if annotation_dict is None:
            self._set_subtype(self.SUB_TYPE)


__all__ = ["PDAnnotationSquiggly"]
