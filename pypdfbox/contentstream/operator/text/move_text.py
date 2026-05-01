from __future__ import annotations

import logging

from pypdfbox.cos import COSBase, COSNumber

from .. import (
    MissingOperandException,
    Operator,
    OperatorName,
    OperatorProcessor,
)

_log = logging.getLogger(__name__)


class MoveText(OperatorProcessor):
    """``Td`` — Move text position by ``(tx, ty)``. Mirrors
    ``org.apache.pdfbox.contentstream.operator.text.MoveText``.

    Operand shape: ``tx ty Td``. Translates the text-line matrix and
    copies the result back to the text matrix.

    Edge cases (parity with upstream):

    * Fewer than two operands raises :class:`MissingOperandException`.
    * Either operand not a :class:`COSNumber` is silently dropped
      (matching upstream's ``instanceof`` short-circuit).
    * When the engine subclass exposes a tracked text-line matrix via
      :meth:`PDFStreamEngine.get_text_line_matrix` and that matrix is
      ``None`` (i.e. the operator landed outside a ``BT``/``ET`` pair
      *and* the subclass actually tracks it), we log a warning and
      skip — mirroring upstream's ``LOG.warn("TextLineMatrix is null,
      ...")`` guard. Cluster #2's base engine has no tracking and
      returns ``None`` unconditionally, so the guard is suppressed
      there to avoid refusing every Td; subclasses that override
      ``set_text_line_matrix_object`` (e.g. the rendering cluster)
      pick up the guard automatically.
    """

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        if len(operands) < 2:
            raise MissingOperandException(operator, operands)
        tx = operands[0]
        ty = operands[1]
        if not isinstance(tx, COSNumber) or not isinstance(ty, COSNumber):
            return
        ctx = self.get_context()
        # Upstream guards on getTextLineMatrix() == null. We mirror the
        # guard but suppress it for the cluster #2 base engine (whose
        # ``get_text_line_matrix`` returns ``None`` unconditionally) so
        # we don't refuse every Td. A subclass that overrides
        # ``get_text_line_matrix`` (the rendering / text-extraction
        # clusters) opts into the guard automatically.
        if self._text_line_matrix_is_tracked(ctx) and (
            ctx.get_text_line_matrix() is None
        ):
            _log.warning(
                "TextLineMatrix is null, %s operator will be ignored",
                self.get_name(),
            )
            return
        ctx.move_text_position(tx.float_value(), ty.float_value())

    @staticmethod
    def _text_line_matrix_is_tracked(ctx: object) -> bool:
        """Return ``True`` only when the engine subclass has overridden
        :meth:`PDFStreamEngine.get_text_line_matrix` — signaling that
        it tracks a real text-line matrix and the upstream null-guard
        is meaningful. The base engine's getter is considered untracked
        so the guard stays inert for cluster #2."""
        from pypdfbox.contentstream.pdf_stream_engine import PDFStreamEngine

        getter = getattr(type(ctx), "get_text_line_matrix", None)
        base_getter = PDFStreamEngine.get_text_line_matrix
        return getter is not None and getter is not base_getter

    def get_name(self) -> str:
        return OperatorName.MOVE_TEXT
