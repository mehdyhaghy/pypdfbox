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

    @staticmethod
    def is_color_space_name(operands: list[COSBase]) -> bool:
        """Return ``True`` iff the operand list is well-formed for ``CS``
        — i.e. a leading :class:`COSName` is present. Mirrors upstream's
        guard ``arguments.get(0) instanceof COSName`` without mutating
        state, so callers (tooling, validators, oracle harnesses) can
        check operand shape before dispatch."""
        if not operands:
            return False
        return isinstance(operands[0], COSName)

    @staticmethod
    def get_color_space_name(operands: list[COSBase]) -> COSName | None:
        """Typed accessor — return the leading :class:`COSName` operand
        if the operand list is well-formed (matches
        :meth:`is_color_space_name`), otherwise ``None``. Equivalent to
        upstream's ``(COSName) arguments.get(0)`` cast guarded by an
        ``instanceof`` check."""
        if not operands:
            return None
        head = operands[0]
        if isinstance(head, COSName):
            return head
        return None

    def resolve_color_space(self, name: COSName) -> Any | None:
        """Resolve ``name`` through the bound engine's
        ``/ColorSpace`` resources, mirroring
        ``context.getResources().getColorSpace(name)`` from upstream
        but tolerating missing context / resources by returning
        ``None`` (so standalone use never raises)."""
        context = self._context
        if context is None:
            return None
        resources = context.get_resources()
        if resources is None:
            return None
        return resources.get_color_space(name)

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        del operator
        name = self.get_color_space_name(operands)
        if name is None:
            return
        context = self._context
        if context is None:
            return
        if not context.is_should_process_color_operators():
            return
        color_space = self.resolve_color_space(name)
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
