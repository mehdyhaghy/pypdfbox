from __future__ import annotations

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSName,
    COSStream,
)
from pypdfbox.pdmodel.pd_resources import PDResources

from .pd_abstract_pattern import PDAbstractPattern

_TYPE: COSName = COSName.TYPE  # type: ignore[attr-defined]
_PATTERN: COSName = COSName.get_pdf_name("Pattern")
_PATTERN_TYPE: COSName = COSName.get_pdf_name("PatternType")
_PAINT_TYPE: COSName = COSName.get_pdf_name("PaintType")
_TILING_TYPE: COSName = COSName.get_pdf_name("TilingType")
_BBOX: COSName = COSName.get_pdf_name("BBox")
_X_STEP: COSName = COSName.get_pdf_name("XStep")
_Y_STEP: COSName = COSName.get_pdf_name("YStep")
_RESOURCES: COSName = COSName.RESOURCES  # type: ignore[attr-defined]


class PDTilingPattern(PDAbstractPattern):
    """Tiling pattern (``/PatternType 1``). Mirrors PDFBox
    ``PDTilingPattern`` lite surface — backed by a ``COSStream`` since
    tiling patterns carry a content stream describing one cell.

    Lite: ``get_b_box`` returns the raw ``COSArray`` (typed
    ``PDRectangle`` wrapping is offered by callers when needed); the
    ``PDContentStream`` mixin (``get_contents`` / ``getContentsForRandomAccess``)
    is deferred to the contentstream parsing cluster."""

    PAINT_COLORED: int = 1
    PAINT_UNCOLORED: int = 2

    TILING_CONSTANT_SPACING: int = 1
    TILING_NO_DISTORTION: int = 2
    TILING_CONSTANT_SPACING_FASTER_TILING: int = 3

    def __init__(self, stream: COSStream | None = None) -> None:
        if stream is None:
            stream = COSStream()
            super().__init__(stream)
            # Fresh stream gets Type/PatternType up front; upstream also
            # attaches an empty PDResources so Adobe Reader will render the
            # pattern (per the PDF spec /Resources is required).
            stream.set_item(_TYPE, _PATTERN)
            stream.set_int(_PATTERN_TYPE, PDAbstractPattern.TYPE_TILING_PATTERN)
            self.set_resources(PDResources())
        else:
            super().__init__(stream)

    # ---------- /PatternType ----------

    def get_pattern_type(self) -> int:
        return PDAbstractPattern.TYPE_TILING_PATTERN

    # ---------- /PaintType ----------

    def get_paint_type(self) -> int:
        return self._dict.get_int(_PAINT_TYPE, 0)

    def set_paint_type(self, paint_type: int) -> None:
        self._dict.set_int(_PAINT_TYPE, paint_type)

    # ---------- /TilingType ----------

    def get_tiling_type(self) -> int:
        return self._dict.get_int(_TILING_TYPE, 0)

    def set_tiling_type(self, tiling_type: int) -> None:
        self._dict.set_int(_TILING_TYPE, tiling_type)

    # ---------- /BBox ----------

    def get_b_box(self) -> COSArray | None:
        """Raw ``/BBox`` array; typed ``PDRectangle`` wrapping is left to
        callers (mirrors PDPage/PDFormXObject surface conventions)."""
        value = self._dict.get_dictionary_object(_BBOX)
        if isinstance(value, COSArray):
            return value
        return None

    def set_b_box(self, bbox: COSArray | None) -> None:
        if bbox is None:
            self._dict.remove_item(_BBOX)
            return
        self._dict.set_item(_BBOX, bbox)

    # ---------- /XStep / /YStep ----------

    def get_x_step(self) -> float:
        return self._dict.get_float(_X_STEP, 0.0)

    def set_x_step(self, x_step: float) -> None:
        self._dict.set_float(_X_STEP, float(x_step))

    def get_y_step(self) -> float:
        return self._dict.get_float(_Y_STEP, 0.0)

    def set_y_step(self, y_step: float) -> None:
        self._dict.set_float(_Y_STEP, float(y_step))

    # ---------- /Resources ----------

    def get_resources(self) -> PDResources | None:
        value = self._dict.get_dictionary_object(_RESOURCES)
        if isinstance(value, COSDictionary):
            return PDResources(value)
        return None

    def set_resources(
        self, resources: PDResources | COSDictionary | None
    ) -> None:
        if resources is None:
            self._dict.remove_item(_RESOURCES)
            return
        target = (
            resources.get_cos_object()
            if isinstance(resources, PDResources)
            else resources
        )
        self._dict.set_item(_RESOURCES, target)


__all__ = ["PDTilingPattern"]
