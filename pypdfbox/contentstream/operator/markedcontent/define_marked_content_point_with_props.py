from __future__ import annotations

from pypdfbox.cos import COSBase, COSName

from .. import MissingOperandException, Operator, OperatorName, OperatorProcessor
from ._props import resolve_property_dict


class DefineMarkedContentPointWithProps(OperatorProcessor):
    """``DP`` — Designate a marked-content point with an associated
    property list. Mirrors
    ``org.apache.pdfbox.contentstream.operator.markedcontent.MarkedContentPointWithProperties``.

    Operand shape: ``<tag> <properties> DP`` where ``<tag>`` is a
    ``COSName`` and ``<properties>`` is either an inline ``COSDictionary``
    or a ``COSName`` referencing the page resources' ``/Properties``
    subdictionary.

    Upstream semantics (mirrored exactly, identical to ``BDC``):

    * fewer than two operands raises :class:`MissingOperandException`;
    * if the first operand is not a ``COSName`` the operator returns;
    * the tag is the **first** operand (``operands[0]``), never the last
      ``COSName`` (which may be the property-list name);
    * if the property list cannot be resolved the operator returns
      **without** notifying the engine.
    """

    OPERATOR_NAME = OperatorName.MARKED_CONTENT_POINT_WITH_PROPS  # "DP"

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        if len(operands) < 2:
            raise MissingOperandException(operator, operands)
        tag = operands[0]
        if not isinstance(tag, COSName):
            return
        properties = resolve_property_dict(operands, self._context)
        if properties is None:
            return
        context = self._context
        if context is None:
            return
        hook = getattr(context, "marked_content_point", None)
        if hook is not None:
            hook(tag, properties)

    def get_name(self) -> str:
        return self.OPERATOR_NAME

    @property
    def name(self) -> str:
        """Pythonic accessor mirroring :class:`Operator.name`. Returns
        the same token as :meth:`get_name`."""
        return self.OPERATOR_NAME
