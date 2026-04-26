from __future__ import annotations

from pypdfbox.cos import COSBase

from .. import Operator
from ..operator_processor import OperatorProcessor


class ShowText(OperatorProcessor):
    """``Tj`` — Show a text string. Mirrors
    ``org.apache.pdfbox.contentstream.operator.text.ShowText``.

    Lite stub used by :class:`OperatorRegistry` — no engine context
    required. The engine-coupled :class:`pypdfbox.contentstream.operator
    .text.show_text.ShowText` carries the real
    ``PDFStreamEngine.show_text_string`` notification; this stub just
    logs the dispatch.

    Filename suffixed with ``_handler`` to avoid colliding with the
    pre-existing ``show_text.py`` in this package — the cluster-#2
    engine-coupled handler module already owns that path.
    """

    OPERATOR_NAME = "Tj"

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        self._log_invocation(operator, operands)
