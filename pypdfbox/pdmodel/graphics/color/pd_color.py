from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos import COSArray, COSFloat, COSInteger, COSName

if TYPE_CHECKING:
    from .pd_color_space import PDColorSpace


class PDColor:
    """A color value, consisting of one or more color components, or for
    pattern color spaces, a name and optional color components. Mirrors
    PDFBox ``org.apache.pdfbox.pdmodel.graphics.color.PDColor``.

    Lite surface: ``to_rgb()`` is deferred until rendering lands.
    """

    def __init__(
        self,
        components: list[float],
        color_space: PDColorSpace,
        pattern: COSName | None = None,
    ) -> None:
        # Defensive copy to keep the instance immutable from the outside.
        self._components: list[float] = [float(c) for c in components]
        self._color_space = color_space
        self._pattern_name = pattern

    # ---------- accessors ----------

    def get_components(self) -> list[float]:
        return list(self._components)

    def get_color_space(self) -> PDColorSpace:
        return self._color_space

    def get_pattern_name(self) -> COSName | None:
        return self._pattern_name

    def is_pattern(self) -> bool:
        return self._pattern_name is not None

    # ---------- COS surface ----------

    def to_cos_array(self) -> COSArray:
        array = COSArray()
        for component in self._components:
            array.add(COSFloat(component))
        if self._pattern_name is not None:
            array.add(self._pattern_name)
        return array

    @classmethod
    def from_cos_array(
        cls,
        array: COSArray,
        color_space: PDColorSpace,
    ) -> PDColor:
        components: list[float] = []
        pattern: COSName | None = None
        for index in range(array.size()):
            item = array.get_object(index)
            if isinstance(item, (COSFloat, COSInteger)):
                components.append(float(item.value))
            elif isinstance(item, COSName):
                pattern = item
        return cls(components, color_space, pattern)


__all__ = ["PDColor"]
