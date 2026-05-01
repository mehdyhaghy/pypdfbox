from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos import COSDictionary, COSName

if TYPE_CHECKING:
    from pypdfbox.pdmodel.graphics.color.pd_color_space import PDColorSpace
    from pypdfbox.pdmodel.pd_resources import PDResources


_S: COSName = COSName.get_pdf_name("S")
_CS: COSName = COSName.get_pdf_name("CS")
_I: COSName = COSName.get_pdf_name("I")
_K: COSName = COSName.get_pdf_name("K")
_TRANSPARENCY: COSName = COSName.get_pdf_name("Transparency")


class PDTransparencyGroupAttributes:
    """
    Transparency group attributes dictionary. Mirrors upstream
    ``org.apache.pdfbox.pdmodel.graphics.form.PDTransparencyGroupAttributes``.

    A transparency group is a group of consecutive objects in a transparency
    stack (PDF 32000-1 §11.6). The group attributes dictionary supplies the
    group's blending color space, isolation flag, and knockout flag.
    """

    def __init__(self, dictionary: COSDictionary | None = None) -> None:
        if dictionary is None:
            dictionary = COSDictionary()
            dictionary.set_item(_S, _TRANSPARENCY)
        self._dictionary = dictionary
        self._color_space: PDColorSpace | None = None

    def get_cos_object(self) -> COSDictionary:
        return self._dictionary

    def get_color_space(
        self, resources: PDResources | None = None
    ) -> PDColorSpace | None:
        """Group color space (``/CS``); ``None`` when absent. Lazily
        resolved via :class:`PDColorSpace`.create and cached. Mirrors
        upstream ``getColorSpace([resources])`` overloads."""
        if self._color_space is None and self._dictionary.contains_key(_CS):
            # Local import keeps the cluster boundary explicit and avoids a
            # cycle through the rest of the graphics package.
            from pypdfbox.pdmodel.graphics.color.pd_color_space import (  # noqa: PLC0415
                PDColorSpace,
            )

            self._color_space = PDColorSpace.create(
                self._dictionary.get_dictionary_object(_CS),
                resources,
            )
        return self._color_space

    def is_isolated(self) -> bool:
        """``/I`` flag (default ``False``). Isolated groups begin with the
        fully transparent image; non-isolated groups begin with the current
        backdrop."""
        return self._dictionary.get_boolean(_I, False)

    def is_knockout(self) -> bool:
        """``/K`` flag (default ``False``). Knockout groups blend with the
        original backdrop; non-knockout groups blend with the current
        backdrop."""
        return self._dictionary.get_boolean(_K, False)
