from __future__ import annotations

from pypdfbox.cos import COSBase

from .. import Operator
from ..operator_processor import OperatorProcessor


class SetFontAndSize(OperatorProcessor):
    """``Tf`` — Set text font and size. Mirrors
    ``org.apache.pdfbox.contentstream.operator.text.SetFontAndSize``.

    Lite stub used by :class:`OperatorRegistry` — logs the dispatch.

    Filename suffixed with ``_handler`` to avoid colliding with the
    pre-existing ``set_font_and_size.py`` engine-coupled module in this
    package.
    """

    OPERATOR_NAME = "Tf"

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        self._log_invocation(operator, operands)
