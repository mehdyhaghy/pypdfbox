from __future__ import annotations

from typing import Any

from pypdfbox.cos import COSArray, COSBase, COSNumber
from pypdfbox.pdmodel.graphics.color import PDColor

from .. import Operator, OperatorName
from ..operator_processor import OperatorProcessor


class SetNonStrokingColor(OperatorProcessor):
    """``sc`` — Same as ``SC`` but for non-stroking operations. Mirrors
    ``org.apache.pdfbox.contentstream.operator.color.SetNonStrokingColor``.

    When bound to an engine with a graphics state, mirrors PDFBox's
    ``getColor`` / ``setColor`` / ``getColorSpace`` hooks through their
    snake_case counterparts.
    """

    OPERATOR_NAME = OperatorName.NON_STROKING_COLOR

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        del operator
        color_space = self.get_color_space()
        if color_space is None:
            return

        component_count = color_space.get_number_of_components()
        if len(operands) < component_count:
            return
        if component_count and not all(
            isinstance(operand, COSNumber) for operand in operands
        ):
            return

        array = COSArray()
        array.add_all(operands)
        self.set_color(PDColor(array, color_space))

    def get_color(self) -> PDColor | None:
        """Return the current non-stroking color, if a graphics state exists."""
        graphics_state = self._graphics_state()
        getter = getattr(graphics_state, "get_non_stroking_color", None)
        if getter is not None:
            return getter()
        return getattr(graphics_state, "non_stroking_color", None)

    def set_color(self, color: PDColor) -> None:
        """Set the current non-stroking color."""
        if self._context is not None:
            self._context.set_non_stroking_color(color)
        graphics_state = self._graphics_state()
        setter = getattr(graphics_state, "set_non_stroking_color", None)
        if setter is not None:
            setter(color)
            return
        if graphics_state is not None:
            graphics_state.non_stroking_color = color

    def get_color_space(self) -> Any | None:
        """Return the current non-stroking color space, if available."""
        graphics_state = self._graphics_state()
        getter = getattr(graphics_state, "get_non_stroking_color_space", None)
        if getter is not None:
            return getter()
        return getattr(graphics_state, "non_stroking_color_space", None)

    def _graphics_state(self) -> Any | None:
        if self._context is None:
            return None
        return self._context.get_graphics_state()
