from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName

from .pd_annotation import PDAnnotation

_MN: COSName = COSName.get_pdf_name("MN")


class PDAnnotationPrinterMark(PDAnnotation):
    """
    Printer's mark annotation — ``/Subtype /PrinterMark``. Mirrors
    ``org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationPrinterMark``.

    Represents a graphic symbol such as a registration target, color bar,
    or cut mark added to a page to assist production personnel during
    pre-press operations (PDF 32000-1:2008 §12.5.6.20, Table 188).

    Printer's mark annotations are not strictly markup annotations — they
    extend :class:`PDAnnotation` directly. The ``/F`` flags should have
    bit 3 (Print) set and bit 6 (NoView) typically set so the marks are
    suppressed on screen but emitted on print.
    """

    SUB_TYPE: str = "PrinterMark"

    def __init__(self, annotation_dict: COSDictionary | None = None) -> None:
        super().__init__(annotation_dict)
        if annotation_dict is None:
            self._set_subtype(self.SUB_TYPE)

    # ---------- /MN (mark name) ----------

    def get_mark_name(self) -> str | None:
        """Return the optional ``/MN`` mark-style name. Free-form arbitrary
        identifier of the mark style (e.g. ``"ColorBar"``)."""
        return self._dict.get_string(_MN)

    def set_mark_name(self, name: str | None) -> None:
        self._dict.set_string(_MN, name)


__all__ = ["PDAnnotationPrinterMark"]
