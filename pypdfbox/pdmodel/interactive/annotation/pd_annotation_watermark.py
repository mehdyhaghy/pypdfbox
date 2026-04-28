from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName

from .pd_annotation import PDAnnotation

_FIXED_PRINT: COSName = COSName.get_pdf_name("FixedPrint")


class PDAnnotationWatermark(PDAnnotation):
    """
    Watermark annotation — ``/Subtype /Watermark``. Mirrors
    ``org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationWatermark``.

    A watermark annotation is used to represent graphics that are expected
    to be printed at a fixed size and position on a page regardless of the
    dimensions of the printed page (PDF 32000-1:2008 §12.5.6.22, Table 190).

    Not a markup annotation — extends :class:`PDAnnotation` directly.

    Subtype-specific entry beyond base:

    * ``/FixedPrint`` — a fixed-print dictionary (Table 191) defining the
      transformation that controls the size and position of the watermark
      relative to the printed page.
    """

    SUB_TYPE: str = "Watermark"

    def __init__(self, annotation_dict: COSDictionary | None = None) -> None:
        super().__init__(annotation_dict)
        if annotation_dict is None:
            self._set_subtype(self.SUB_TYPE)

    # ---------- /FixedPrint (fixed print dictionary) ----------

    def get_fixed_print(self) -> COSDictionary | None:
        """Return the raw ``/FixedPrint`` dictionary or ``None`` when absent.

        A typed ``PDFixedPrint`` wrapper is deferred — see ``CHANGES.md``."""
        value = self._dict.get_dictionary_object(_FIXED_PRINT)
        if isinstance(value, COSDictionary):
            return value
        return None

    def set_fixed_print(self, value: COSDictionary | None) -> None:
        if value is None:
            self._dict.remove_item(_FIXED_PRINT)
            return
        if isinstance(value, COSDictionary):
            self._dict.set_item(_FIXED_PRINT, value)
            return
        if hasattr(value, "get_cos_object"):
            cos = value.get_cos_object()
            if not isinstance(cos, COSDictionary):
                raise TypeError(
                    "set_fixed_print expects a COSDictionary-backed wrapper"
                )
            self._dict.set_item(_FIXED_PRINT, cos)
            return
        raise TypeError(
            "set_fixed_print expects None, COSDictionary, or wrapper exposing "
            f"get_cos_object(); got {type(value).__name__}"
        )


__all__ = ["PDAnnotationWatermark"]
