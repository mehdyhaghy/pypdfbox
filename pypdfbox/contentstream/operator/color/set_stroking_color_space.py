from __future__ import annotations

from typing import Any

from pypdfbox.cos import COSBase, COSName

from .. import Operator, OperatorName
from ..operator_processor import OperatorProcessor


class SetStrokingColorSpace(OperatorProcessor):
    """``CS`` — Set the current colour space to use for stroking
    operations. Mirrors
    ``org.apache.pdfbox.contentstream.operator.color.SetStrokingColorSpace``.

    When bound to a stream engine the operand is resolved through
    :meth:`PDFStreamEngine.get_resources` (the ``/ColorSpace`` resource
    dictionary), and the resolved colour space is installed onto the
    graphics state along with that colour space's initial colour, so
    subsequent ``SC`` / ``SCN`` operators can consume it. Standalone
    (no engine) the operator is a no-op so the registry can still
    dispatch it for tooling.
    """

    OPERATOR_NAME = OperatorName.STROKING_COLORSPACE

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        del operator
        if not operands:
            return
        name = operands[0]
        if not isinstance(name, COSName):
            return
        context = self._context
        if context is None:
            return
        if not context.is_should_process_color_operators():
            return
        resources = context.get_resources()
        if resources is None:
            return
        color_space = resources.get_color_space(name)
        if color_space is None:
            return
        graphics_state = context.get_graphics_state()
        setter = getattr(graphics_state, "set_stroking_color_space", None)
        if setter is not None:
            setter(color_space)
        else:
            self._set_attr(graphics_state, "stroking_color_space", color_space)
        # Mirror upstream: also reset the stroking colour to the new
        # colour space's initial colour value.
        get_initial = getattr(color_space, "get_initial_color", None)
        if get_initial is not None:
            initial = get_initial()
            color_setter = getattr(graphics_state, "set_stroking_color", None)
            if color_setter is not None:
                color_setter(initial)
            else:
                self._set_attr(graphics_state, "stroking_color", initial)
            engine_setter = getattr(context, "set_stroking_color", None)
            if engine_setter is not None:
                engine_setter(initial)

    @staticmethod
    def _set_attr(target: Any | None, attr: str, value: Any) -> None:
        if target is not None:
            try:
                setattr(target, attr, value)
            except AttributeError:
                # Slotted graphics-state implementations without the
                # attribute; mirror upstream's silent no-op.
                pass
