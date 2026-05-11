"""Custom ``gs`` operator that pins alpha to 1.0.

Ported from the inner class
``OpaquePDFRenderer.OpaqueSetGraphicsStateParameters``
(``examples/src/main/java/org/apache/pdfbox/examples/printing/OpaquePDFRenderer.java``
lines 176-217). Identical to the upstream
``SetGraphicsStateParameters`` operator but forces both ``ca`` and
``CA`` to 1.0 before merging the ExtGState dict.
"""

from __future__ import annotations

import logging
from typing import Any

from pypdfbox.contentstream.operator.operator_processor import OperatorProcessor
from pypdfbox.contentstream.operator_name import OperatorName
from pypdfbox.contentstream.operator_processor import MissingOperandException
from pypdfbox.cos.cos_base import COSBase
from pypdfbox.cos.cos_name import COSName

_log = logging.getLogger(__name__)


class OpaqueSetGraphicsStateParameters(OperatorProcessor):
    """``gs`` operator that strips transparency."""

    OPERATOR_NAME = OperatorName.SET_GRAPHICS_STATE_PARAMS

    def __init__(self, context: Any) -> None:
        super().__init__(context)

    def process(self, operator: Any, arguments: list[COSBase]) -> None:
        if not arguments:
            raise MissingOperandException(operator, arguments)
        base0 = arguments[0]
        if not isinstance(base0, COSName):
            return

        graphics_name = base0
        context = self.get_context()
        if context is None:
            return
        gs = context.get_resources().get_ext_g_state(graphics_name)
        if gs is None:
            _log.error(
                "name for 'gs' operator not found in resources: /%s",
                graphics_name.get_name(),
            )
            return
        gs.set_non_stroking_alpha_constant(1.0)
        gs.set_stroking_alpha_constant(1.0)
        gs.copy_into_graphics_state(context.get_graphics_state())

    def get_name(self) -> str:
        return OperatorName.SET_GRAPHICS_STATE_PARAMS
