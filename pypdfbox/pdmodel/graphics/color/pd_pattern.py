from __future__ import annotations

from pypdfbox.cos import COSArray, COSBase, COSName

from .pd_color import PDColor
from .pd_color_space import PDColorSpace


class PDPattern(PDColorSpace):
    """A Pattern color space. Mirrors PDFBox
    ``org.apache.pdfbox.pdmodel.graphics.color.PDPattern``.

    Lite surface: pattern dictionary lookup, tiling/shading dispatch,
    and ``to_rgb`` rendering are deferred until the pattern + rendering
    modules land. The underlying color space (uncolored tiling case)
    is exposed through ``get_underlying_color_space``.
    """

    NAME: str = "Pattern"

    def __init__(
        self,
        underlying_color_space: PDColorSpace | None = None,
    ) -> None:
        # Pattern can be either:
        #   /Pattern                         (colored, name form)
        #   [/Pattern <underlying CS>]       (uncolored tiling)
        if underlying_color_space is None:
            super().__init__(None)
        else:
            arr = COSArray()
            arr.add(COSName.get_pdf_name(self.NAME))
            ucs = underlying_color_space.get_cos_object()
            if ucs is not None:
                arr.add(ucs)
            super().__init__(arr)
        self._underlying = underlying_color_space
        self._initial_color = PDColor([], self)

    # ---------- COS surface ----------

    def get_cos_object(self) -> COSBase:
        if self._array is not None:
            return self._array
        return COSName.get_pdf_name(self.NAME)

    # ---------- abstract surface ----------

    def get_name(self) -> str:
        return self.NAME

    def get_number_of_components(self) -> int:
        # Upstream throws UnsupportedOperationException — components are
        # only meaningful for the underlying CS in the uncolored tiling
        # case. We return 0 so callers that just want a size get a sane
        # answer; explicit lookups should ask the underlying CS instead.
        return 0

    def get_initial_color(self) -> PDColor:
        return self._initial_color

    # ---------- pattern-specific ----------

    def get_underlying_color_space(self) -> PDColorSpace | None:
        return self._underlying

    def __str__(self) -> str:
        return self.NAME


__all__ = ["PDPattern"]
