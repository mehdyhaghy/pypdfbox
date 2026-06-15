from __future__ import annotations

from pypdfbox.cos import COSBase, COSName

from .. import MissingOperandException, Operator
from ..operator_processor import OperatorProcessor


class ShadingFill(OperatorProcessor):
    """``sh`` — Paint the shape and colour shading described by the
    shading dictionary referenced by the named resource (``/Shading``
    sub-resource on the current page or form XObject). Mirrors
    ``org.apache.pdfbox.contentstream.operator.graphics.ShadingFill``.

    Operand validation matches upstream bytecode
    (``ShadingFill.process`` in PDFBox 3.0.7) exactly:

    * Fewer than one operand raises :class:`MissingOperandException`.
    * If the first operand is not a :class:`COSName`, upstream *also*
      raises :class:`MissingOperandException` — it does **not** silently
      skip. ``sh`` differs here from the path operators (``MoveTo``,
      ``LineTo``, ``CurveTo``, ``AppendRectangleToPath``), which use
      ``checkArrayTypesClass`` to skip non-number operand stacks; ``sh``
      has no such leniency in upstream, so a non-name leading operand is
      a missing-operand error. The exception is logged and swallowed by
      ``PDFStreamEngine.operatorException`` (it is a
      ``MissingOperandException``), so the stream still continues — the
      net effect through the engine is that ``shadingFill`` is not
      invoked, matching the live oracle.
    * No shading-resource lookup happens in the operator itself.
      Upstream calls ``getGraphicsContext().shadingFill(shadingName)``
      unconditionally once the operand is a name; an unknown shading
      name, a missing ``/Shading`` sub-dict, a wrong-typed ``/Shading``
      entry, and even ``null`` resources are all resolved (or skipped)
      inside the ``shadingFill`` hook downstream, not here.

    The shading-resource lookup and dispatch to the shading-type
    painter lands with the rendering cluster; until then a successful
    validation reduces to the existing debug-log no-op.
    """

    OPERATOR_NAME = "sh"

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        if len(operands) < 1:
            raise MissingOperandException(operator, operands)
        if not isinstance(operands[0], COSName):
            raise MissingOperandException(operator, operands)
        self._log_invocation(operator, operands)
