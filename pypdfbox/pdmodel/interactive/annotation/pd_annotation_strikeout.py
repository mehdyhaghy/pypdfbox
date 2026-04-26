from __future__ import annotations

from pypdfbox.cos import COSDictionary

from .pd_annotation_text_markup import PDAnnotationTextMarkup


class PDAnnotationStrikeout(PDAnnotationTextMarkup):
    """``/Subtype /StrikeOut`` text markup annotation. Mirrors
    ``org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationStrikeout``.

    Note the PDF spec capitalization: ``StrikeOut`` (not ``Strikeout``).
    """

    SUB_TYPE: str = "StrikeOut"

    def __init__(self, annotation_dict: COSDictionary | None = None) -> None:
        super().__init__(annotation_dict)
        if annotation_dict is None:
            self._set_subtype(self.SUB_TYPE)


__all__ = ["PDAnnotationStrikeout"]
