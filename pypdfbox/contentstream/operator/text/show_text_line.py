from __future__ import annotations

from pypdfbox.cos import COSBase

from .. import (
    MissingOperandException,
    Operator,
    OperatorName,
    OperatorProcessor,
)


class ShowTextLine(OperatorProcessor):
    """``'`` (apostrophe) — Move to next line and show text. Mirrors
    ``org.apache.pdfbox.contentstream.operator.text.ShowTextLine``.

    Operand shape: ``<string> '``. Equivalent to ``T*`` followed by
    ``Tj``. Upstream re-enters the engine via ``processOperator`` for
    each step; we do the same so a subclass that registered just
    :class:`ShowText` (without :class:`ShowTextLine`) still observes
    the underlying ``Tj`` notification.

    Upstream's ``ShowTextLine.process`` opens with
    ``if (arguments.size() < 1) throw new MissingOperandException(...)``
    *before* dispatching either sub-operator, so an operand-less ``'``
    is rejected atomically and the synthetic ``T*`` line-move never
    fires. We mirror that guard up front; without it the prior
    implementation dispatched ``T*`` (advancing the text-line matrix by
    one leading) and only then hit the missing-operand error inside the
    delegated ``Tj``, leaking a spurious vertical shift.
    """

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        if not operands:
            raise MissingOperandException(operator, operands)
        ctx = self.get_context()
        ctx.process_operator(OperatorName.NEXT_LINE, None)
        ctx.process_operator(OperatorName.SHOW_TEXT, operands)

    def get_name(self) -> str:
        return OperatorName.SHOW_TEXT_LINE
