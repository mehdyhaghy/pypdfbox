from __future__ import annotations

from pypdfbox.cos import COSBase

from .. import Operator, OperatorName, OperatorProcessor
from ._props import extract_tag


class BeginMarkedContent(OperatorProcessor):
    """``BMC`` — Begin a marked-content sequence. Mirrors
    ``org.apache.pdfbox.contentstream.operator.markedcontent.BeginMarkedContentSequence``.

    Operand shape: ``<tag> BMC`` where ``<tag>`` is a ``COSName``.
    Forwards the parsed tag to the engine's
    :meth:`begin_marked_content_sequence` hook (when the engine exposes
    one — text-extraction subclasses such as
    :class:`PDFMarkedContentExtractor` do; the bare
    :class:`PDFStreamEngine` and the graphics engine register the
    operator only for the upstream-faithful name surface and do not
    define the hook).

    No properties are associated with a ``BMC`` sequence — the property
    list arrives on the ``BDC`` form (see
    :class:`BeginMarkedContentWithProps`). The hook is therefore called
    with ``properties=None``.
    """

    OPERATOR_NAME = OperatorName.BEGIN_MARKED_CONTENT  # "BMC"

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        del operator  # unused — operator name fixed by registration
        tag = extract_tag(operands)
        context = self._context
        if context is None:
            return
        hook = getattr(context, "begin_marked_content_sequence", None)
        if hook is not None:
            hook(tag, None)

    def get_name(self) -> str:
        return self.OPERATOR_NAME

    @property
    def name(self) -> str:
        """Pythonic accessor mirroring :class:`Operator.name`. Returns
        the same token as :meth:`get_name` — the upstream-faithful path
        is :meth:`get_name`; :attr:`name` is provided for symmetry with
        :class:`Operator` and idiomatic Python attribute access."""
        return self.OPERATOR_NAME
