from __future__ import annotations

from pypdfbox.cos import COSBase

from .. import Operator, OperatorName, OperatorProcessor
from ._props import extract_tag


class DefineMarkedContentPoint(OperatorProcessor):
    """``MP`` — Designate a marked-content point. Mirrors
    ``org.apache.pdfbox.contentstream.operator.markedcontent.MarkedContentPoint``.

    Operand shape: ``<tag> MP`` where ``<tag>`` is a ``COSName``. A
    marked-content point is a single tagged location in the content
    stream — unlike ``BMC`` / ``BDC`` it does not open a sequence and is
    not balanced by ``EMC``.

    Forwards ``(tag, None)`` to the engine's
    :meth:`marked_content_point` hook when the engine exposes one.
    """

    OPERATOR_NAME = OperatorName.MARKED_CONTENT_POINT  # "MP"

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        del operator  # unused — operator name fixed by registration
        tag = extract_tag(operands)
        context = self._context
        if context is None:
            return
        hook = getattr(context, "marked_content_point", None)
        if hook is not None:
            hook(tag, None)

    def get_name(self) -> str:
        return self.OPERATOR_NAME

    @property
    def name(self) -> str:
        """Pythonic accessor mirroring :class:`Operator.name`. Returns
        the same token as :meth:`get_name`."""
        return self.OPERATOR_NAME
