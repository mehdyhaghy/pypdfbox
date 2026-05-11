"""``Do`` — Draws an XObject.

Mirrors ``org.apache.pdfbox.contentstream.operator.DrawObject`` (PDFBox 3.x;
Java path
``pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/DrawObject.java``).
"""

from __future__ import annotations

import logging

from pypdfbox.cos import COSBase, COSName

from . import MissingOperandException, Operator, OperatorName
from .operator_processor import OperatorProcessor

_log = logging.getLogger(__name__)


class DrawObject(OperatorProcessor):
    """``Do`` — draw the XObject named by the operand.

    Operand shape: ``<name> Do`` where ``<name>`` references either an
    image XObject (short-circuited during text extraction — upstream
    ``getResources().isImageXObject(name)``) or a form / transparency
    group XObject. Recursion depth is capped at 50 to mirror the
    upstream guard.
    """

    OPERATOR_NAME = OperatorName.DRAW_OBJECT

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        if not operands:
            raise MissingOperandException(operator, operands)
        base0 = operands[0]
        if not isinstance(base0, COSName):
            return
        name: COSName = base0

        context = self._context
        if context is None:
            return
        resources = context.get_resources()
        if resources is None:
            return

        is_image = getattr(resources, "is_image_x_object", None)
        if is_image is not None and is_image(name):
            return

        get_x = getattr(resources, "get_x_object", None)
        if get_x is None:
            return
        xobject = get_x(name)

        if _is_form_xobject(xobject):
            try:
                context.increase_level()
                if context.get_level() > 50:
                    _log.error("recursion is too deep, skipping form XObject")
                    return
                if _is_transparency_group(xobject):
                    show = getattr(context, "show_transparency_group", None)
                    if show is not None:
                        show(xobject)
                else:
                    show = getattr(context, "show_form", None)
                    if show is not None:
                        show(xobject)
            finally:
                context.decrease_level()

    def get_name(self) -> str:
        return OperatorName.DRAW_OBJECT


def _is_form_xobject(obj: object) -> bool:
    return type(obj).__name__ in {
        "PDFormXObject",
        "PDTransparencyGroup",
    } or getattr(obj, "is_form_xobject", False)


def _is_transparency_group(obj: object) -> bool:
    return type(obj).__name__ == "PDTransparencyGroup"


__all__ = ["DrawObject"]
