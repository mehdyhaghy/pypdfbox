from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos import COSArray, COSFloat, COSInteger

if TYPE_CHECKING:
    from ..pd_annotation import PDAnnotation
    from ..pd_border_style_dictionary import PDBorderStyleDictionary


class AnnotationBorder:
    """Collected border-info helper for annotation appearance handlers.
    Mirrors ``org.apache.pdfbox.pdmodel.interactive.annotation.handlers.AnnotationBorder``.

    Carries the resolved stroke ``width``, optional ``dash_array``, and an
    ``underline`` flag. Built from either a ``PDBorderStyleDictionary``
    (``/BS``) when present, or the legacy ``/Border`` array
    ``[hRadius vRadius width dashArray]``.
    """

    def __init__(self) -> None:
        self.dash_array: list[float] | None = None
        self.underline: bool = False
        self.width: float = 0.0

    @staticmethod
    def get_annotation_border(
        annotation: "PDAnnotation",
        border_style: "PDBorderStyleDictionary | None",
    ) -> "AnnotationBorder":
        # Local import to avoid circulars at module-load time.
        from ..pd_border_style_dictionary import PDBorderStyleDictionary

        ab = AnnotationBorder()
        if border_style is None:
            border = annotation.get_border()
            if border is not None and border.size() >= 3:
                base = border.get_object(2)
                if isinstance(base, (COSFloat, COSInteger)):
                    ab.width = float(base.value)
            if border is not None and border.size() > 3:
                base3 = border.get_object(3)
                if isinstance(base3, COSArray):
                    ab.dash_array = base3.to_float_array()
        else:
            ab.width = border_style.get_width()
            style = border_style.get_style()
            if style == PDBorderStyleDictionary.STYLE_DASHED:
                dash = border_style.get_dash_style()
                if dash is not None:
                    ab.dash_array = list(dash.get_dash_array())
            if style == PDBorderStyleDictionary.STYLE_UNDERLINE:
                ab.underline = True
        # An all-zero dash array is meaningless; drop it (mirrors upstream).
        if ab.dash_array is not None and all(
            float(v) == 0.0 for v in ab.dash_array
        ):
            ab.dash_array = None
        return ab


__all__ = ["AnnotationBorder"]
