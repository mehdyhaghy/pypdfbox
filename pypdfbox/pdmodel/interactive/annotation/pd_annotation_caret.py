from __future__ import annotations

from pypdfbox.cos import COSDictionary

from .pd_annotation_markup import PDAnnotationMarkup


class PDAnnotationCaret(PDAnnotationMarkup):
    """``/Subtype /Caret`` annotation. Mirrors
    ``org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationCaret``.
    """

    SUB_TYPE: str = "Caret"

    def __init__(self, annotation_dict: COSDictionary | None = None) -> None:
        super().__init__(annotation_dict)
        if annotation_dict is None:
            self._set_subtype(self.SUB_TYPE)


__all__ = ["PDAnnotationCaret"]
