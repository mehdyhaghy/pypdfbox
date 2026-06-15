from __future__ import annotations

from pypdfbox.cos import COSBase, COSName

from .. import MissingOperandException, Operator, OperatorName, OperatorProcessor
from ._props import resolve_property_dict


class BeginMarkedContentWithProps(OperatorProcessor):
    """``BDC`` — Begin a marked-content sequence with an associated
    property list. Mirrors
    ``org.apache.pdfbox.contentstream.operator.markedcontent.BeginMarkedContentSequenceWithProperties``.

    Operand shape: ``<tag> <properties> BDC`` where ``<tag>`` is a
    ``COSName`` and ``<properties>`` is either an inline ``COSDictionary``
    or a ``COSName`` referencing the page resources' ``/Properties``
    subdictionary. Inline dictionary wins; otherwise the name is looked
    up via :meth:`PDResources.get_property_list` on the engine's current
    resources.

    Upstream semantics (mirrored exactly):

    * fewer than two operands raises :class:`MissingOperandException`
      (the engine catches it, logs, and continues — no sequence opens);
    * if the first operand is not a ``COSName`` the operator returns
      without opening a sequence;
    * the tag is the **first** operand (``operands[0]``), *not* the last
      ``COSName`` — the property operand of the ``/Name`` form is itself
      a ``COSName`` and must not be mistaken for the tag;
    * if the property list cannot be resolved to a ``COSDictionary``
      (unknown ``/Name``, wrong operand type, ``null`` lookup) the
      operator returns **without** opening a sequence — upstream does not
      push a marked-content node for an unresolved property list.
    """

    OPERATOR_NAME = OperatorName.BEGIN_MARKED_CONTENT_SEQ  # "BDC"

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
        hook = getattr(context, "begin_marked_content_sequence", None)
        if hook is not None:
            hook(tag, properties)

    def get_name(self) -> str:
        return self.OPERATOR_NAME

    @property
    def name(self) -> str:
        """Pythonic accessor mirroring :class:`Operator.name`. Returns
        the same token as :meth:`get_name`."""
        return self.OPERATOR_NAME
