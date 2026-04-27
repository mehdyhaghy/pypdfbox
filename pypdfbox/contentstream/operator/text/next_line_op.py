from __future__ import annotations

from pypdfbox.cos import COSBase, COSFloat

from .. import Operator, OperatorName, OperatorProcessor


class NextLine(OperatorProcessor):
    """``T*`` — Move to the start of the next text line. Mirrors
    ``org.apache.pdfbox.contentstream.operator.text.NextLine``.

    Operand shape: zero operands. Equivalent to ``0 -leading Td``, where
    ``leading`` is the current text leading. Engine-coupled handler:
    re-enters the engine via ``processOperator(Td, [0, -leading])`` so
    that any registered :class:`MoveText` handler observes the
    decomposition (matching upstream's
    ``getContext().processOperator(MOVE_TEXT, ...)`` call).

    Cluster #2's base engine doesn't track leading; subclasses that do
    override :meth:`PDFStreamEngine.get_text_leading`. When that
    accessor is absent we fall back to ``0`` — the underlying ``Td``
    still fires for downstream observers, just without a vertical shift.

    Filename suffixed with ``_op`` to avoid colliding with the pre-
    existing ``next_line.py`` lite-stub module routed via
    :class:`OperatorRegistry`.
    """

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        ctx = self.get_context()
        leading = 0.0
        leading_accessor = getattr(ctx, "get_text_leading", None)
        if callable(leading_accessor):
            try:
                leading = float(leading_accessor())
            except (TypeError, ValueError):
                leading = 0.0
        ctx.process_operator(
            OperatorName.MOVE_TEXT,
            [COSFloat(0.0), COSFloat(-leading)],
        )

    def get_name(self) -> str:
        return OperatorName.NEXT_LINE
