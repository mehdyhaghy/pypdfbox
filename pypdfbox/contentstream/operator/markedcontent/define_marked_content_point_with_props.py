from __future__ import annotations

from pypdfbox.cos import COSBase, COSDictionary

from .. import Operator, OperatorName, OperatorProcessor
from ._props import extract_tag, resolve_property_dict


class DefineMarkedContentPointWithProps(OperatorProcessor):
    """``DP`` — Designate a marked-content point with an associated
    property list. Mirrors
    ``org.apache.pdfbox.contentstream.operator.markedcontent.MarkedContentPointWithProperties``.

    Operand shape: ``<tag> <properties> DP`` where ``<tag>`` is a
    ``COSName`` and ``<properties>`` is either an inline ``COSDictionary``
    or a ``COSName`` referencing the page resources' ``/Properties``
    subdictionary.

    Forwards ``(tag, properties)`` to the engine's
    :meth:`marked_content_point` hook when the engine exposes one.
    Property resolution mirrors :class:`BeginMarkedContentWithProps`.
    """

    OPERATOR_NAME = OperatorName.MARKED_CONTENT_POINT_WITH_PROPS  # "DP"

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        del operator  # unused — operator name fixed by registration
        tag = extract_tag(operands)
        properties = self._resolve_properties(operands)
        context = self._context
        if context is None:
            return
        hook = getattr(context, "marked_content_point", None)
        if hook is not None:
            hook(tag, properties)

    def _resolve_properties(
        self, operands: list[COSBase]
    ) -> COSDictionary | None:
        return resolve_property_dict(operands, self._context)

    def get_name(self) -> str:
        return self.OPERATOR_NAME

    @property
    def name(self) -> str:
        """Pythonic accessor mirroring :class:`Operator.name`. Returns
        the same token as :meth:`get_name`."""
        return self.OPERATOR_NAME
