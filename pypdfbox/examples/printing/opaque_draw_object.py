"""Custom ``Do`` operator that suppresses transparency groups.

Ported from the inner class
``OpaquePDFRenderer.OpaqueDrawObject``
(``examples/src/main/java/org/apache/pdfbox/examples/printing/OpaquePDFRenderer.java``
lines 114-172). The Java demo is copied from
``org.apache.pdfbox.contentstream.operator.graphics.DrawObject`` but
calls ``showForm`` instead of ``showTransparencyGroup`` — useful for
printers that handle flat artwork much faster than transparency.
"""

from __future__ import annotations

import logging
from typing import Any

from pypdfbox.contentstream.operator.graphics.graphics_operator_processor import (
    GraphicsOperatorProcessor,
)
from pypdfbox.contentstream.operator_name import OperatorName
from pypdfbox.contentstream.operator_processor import MissingOperandException
from pypdfbox.cos.cos_base import COSBase
from pypdfbox.cos.cos_name import COSName
from pypdfbox.pdmodel.missing_resource_exception import MissingResourceException

_log = logging.getLogger(__name__)

# Upstream constant (line 154).
_MAX_FORM_RECURSION_DEPTH = 50


class OpaqueDrawObject(GraphicsOperatorProcessor):
    """``Do`` operator that bypasses transparency groups."""

    OPERATOR_NAME = OperatorName.DRAW_OBJECT

    def __init__(self, context: Any) -> None:
        super().__init__(context)

    def process(self, operator: Any, operands: list[COSBase]) -> None:
        if not operands:
            raise MissingOperandException(operator, operands)
        base0 = operands[0]
        if not isinstance(base0, COSName):
            return
        object_name = base0

        context = self.get_graphics_context()
        if context is None:
            return
        resources = context.get_resources()
        xobject = resources.get_x_object(object_name)
        if xobject is None:
            raise MissingResourceException(
                f"Missing XObject: {object_name.get_name()}"
            )

        # Avoid hard imports for type checks — the example needs to keep
        # working even if the rendering cluster ships extra subclasses.
        type_name = type(xobject).__name__
        if type_name == "PDImageXObject":
            context.draw_image(xobject)
        elif type_name == "PDFormXObject":
            try:
                context.increase_level()
                if context.get_level() > _MAX_FORM_RECURSION_DEPTH:
                    _log.error("recursion is too deep, skipping form XObject")
                    return
                context.show_form(xobject)
            finally:
                context.decrease_level()

    def get_name(self) -> str:
        return OperatorName.DRAW_OBJECT
