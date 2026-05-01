from __future__ import annotations

from pypdfbox.cos import COSArray, COSBase, COSNumber
from pypdfbox.pdmodel.graphics.color import PDColor, PDPattern

from .. import Operator, OperatorName
from .set_non_stroking_color import SetNonStrokingColor


class SetNonStrokingColorN(SetNonStrokingColor):
    """``scn`` — Same as ``SCN`` but for non-stroking operations.
    Mirrors ``org.apache.pdfbox.contentstream.operator.color.SetNonStrokingColorN``.

    Inherits the ``get_color`` / ``set_color`` / ``get_color_space``
    hooks from :class:`SetNonStrokingColor` and overrides :meth:`process`
    to additionally handle the Pattern colour space (whose operand
    layout — ``[c1 ... cn name]`` or ``[name]`` — is parsed by
    :class:`PDColor`'s ``COSArray`` constructor).
    """

    OPERATOR_NAME = OperatorName.NON_STROKING_COLOR_N

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        del operator
        color_space = self.get_color_space()
        if color_space is None:
            return

        if not isinstance(color_space, PDPattern):
            if len(operands) < color_space.get_number_of_components():
                return
            if not all(isinstance(operand, COSNumber) for operand in operands):
                # PDFBOX-5851: a non-numeric operand in a non-Pattern
                # colour space means the Pattern colour space is missing
                # from /Resources — set an invalid (empty-component, no
                # colour-space) PDColor so that downstream paint logic
                # can render it as transparent rather than crashing.
                self.set_color(PDColor([], None))  # type: ignore[arg-type]
                return

        array = COSArray()
        array.add_all(operands)
        self.set_color(PDColor(array, color_space))
