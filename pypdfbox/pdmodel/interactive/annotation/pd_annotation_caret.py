from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName

from .pd_annotation_markup import PDAnnotationMarkup

_RD: COSName = COSName.get_pdf_name("RD")
_SY: COSName = COSName.get_pdf_name("Sy")


class PDAnnotationCaret(PDAnnotationMarkup):
    """``/Subtype /Caret`` annotation. Mirrors
    ``org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationCaret``.

    A caret annotation is a visual symbol that indicates the presence of
    text edits (PDF 32000-1:2008 §12.5.6.11, Table 180). Extends
    :class:`PDAnnotationMarkup` so review-workflow metadata (``/CreationDate``,
    ``/Subj``, ``/IRT``, ``/CA``, …) come for free.

    Subtype-specific entries beyond markup base:

    * ``/RD`` — rectangle differences (``[lx ly rx ry]`` — distances from
      ``/Rect`` edges to the actual caret) (Table 180).
    * ``/Sy`` — symbol drawn inside the rectangle. ``"P"`` (paragraph) or
      ``"None"`` (default).
    """

    SUB_TYPE: str = "Caret"

    # /Sy values per spec Table 180.
    SY_PARAGRAPH: str = "P"
    SY_NONE: str = "None"  # spec default

    def __init__(self, annotation_dict: COSDictionary | None = None) -> None:
        super().__init__(annotation_dict)
        if annotation_dict is None:
            self._set_subtype(self.SUB_TYPE)

    # ---------- /RD (rectangle differences) ----------

    def get_rectangle_differences(self) -> list[float] | None:
        """Return the four-float ``/RD`` rectangle-difference array
        (``[lx ly rx ry]``) or ``None`` when absent."""
        value = self._dict.get_dictionary_object(_RD)
        if isinstance(value, COSArray):
            return value.to_float_array()
        return None

    def set_rectangle_differences(
        self, rd: list[float] | tuple[float, ...] | None
    ) -> None:
        if rd is None:
            self._dict.remove_item(_RD)
            return
        if len(rd) != 4:
            raise ValueError(
                f"/RD must be a 4-element [lx ly rx ry] array; got {len(rd)} elements"
            )
        self._dict.set_item(_RD, COSArray([COSFloat(float(v)) for v in rd]))

    def get_rect_differences(self) -> list[float] | None:
        """Upstream-spelled alias for ``get_rectangle_differences``."""
        return self.get_rectangle_differences()

    def set_rect_differences(
        self, rd: list[float] | tuple[float, ...] | None
    ) -> None:
        """Upstream-spelled alias for ``set_rectangle_differences``."""
        self.set_rectangle_differences(rd)

    # ---------- /Sy (caret symbol) ----------

    def get_symbol(self) -> str:
        """Return the caret ``/Sy`` symbol name. Defaults to ``"None"`` per spec."""
        value = self._dict.get_name(_SY)
        return value if value is not None else self.SY_NONE

    def set_symbol(self, symbol: str | None) -> None:
        if symbol is None:
            self._dict.remove_item(_SY)
            return
        self._dict.set_name(_SY, symbol)


__all__ = ["PDAnnotationCaret"]
