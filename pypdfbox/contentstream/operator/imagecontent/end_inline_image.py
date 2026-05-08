from __future__ import annotations

from pypdfbox.cos import COSBase

from ...operator_name import OperatorName
from .. import Operator
from ..operator_processor import OperatorProcessor


class EndInlineImage(OperatorProcessor):
    """``EI`` — End an inline image object. Mirrors the ``EI`` operator
    closure in
    ``org.apache.pdfbox.contentstream.operator.BeginInlineImage``.

    Lite stub kept for registry parity. Like ``ID``, ``EI`` is never
    dispatched as a standalone operator at the engine level — the
    parser (:class:`pypdfbox.pdfparser.PDFStreamParser`) terminates the
    inline-image segment at the ``EI`` boundary (whitespace before
    ``EI`` plus whitespace/EOL after, with a binary-data follow-on
    probe so embedded ``EI`` byte pairs inside image bytes don't
    terminate prematurely) and discards the ``EI`` token. The
    inline-image construction lives in
    :meth:`PDFStreamEngine.process_operator`, which builds a
    :class:`pypdfbox.pdmodel.graphics.image.PDInlineImage` from the
    parser-collated ``BI`` operator and forwards it to
    :meth:`PDFStreamEngine.show_inline_image`.
    """

    OPERATOR_NAME = OperatorName.END_INLINE_IMAGE

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        self._log_invocation(operator, operands)
