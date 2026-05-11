"""``BDC`` — Begin a marked-content sequence with property list.

Mirrors
``org.apache.pdfbox.contentstream.operator.markedcontent.BeginMarkedContentSequenceWithProperties``
(PDFBox 3.x; Java path:
``pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/markedcontent``
``/BeginMarkedContentSequenceWithProperties.java``).
"""

from __future__ import annotations

from pypdfbox.cos import COSBase, COSDictionary, COSName

from .. import MissingOperandException, Operator, OperatorName, OperatorProcessor


class BeginMarkedContentSequenceWithProperties(OperatorProcessor):
    """``BDC`` — pop ``(tag, props)`` from the operand stack and forward
    them to :meth:`PDFStreamEngine.begin_marked_content_sequence`.

    Per upstream the second operand is either an inline ``COSDictionary``
    or a ``COSName`` resolved against the page resources' ``/Properties``
    sub-dictionary (PDFBOX-5980, SO79549651).
    """

    OPERATOR_NAME = OperatorName.BEGIN_MARKED_CONTENT_SEQ

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        if len(operands) < 2:
            raise MissingOperandException(operator, operands)
        if not isinstance(operands[0], COSName):
            return
        context = self._context
        if context is None:
            return
        tag = operands[0]
        op1 = operands[1]
        prop_dict: COSDictionary | None = None
        if isinstance(op1, COSName):
            resources = context.get_resources()
            if resources is not None:
                get_props = getattr(resources, "get_properties", None)
                prop = get_props(op1) if get_props is not None else None
                if prop is not None:
                    get_cos = getattr(prop, "get_cos_object", None)
                    prop_dict = get_cos() if get_cos is not None else None
        elif isinstance(op1, COSDictionary):
            prop_dict = op1
        if prop_dict is None:
            return
        hook = getattr(context, "begin_marked_content_sequence", None)
        if hook is not None:
            hook(tag, prop_dict)

    def get_name(self) -> str:
        return OperatorName.BEGIN_MARKED_CONTENT_SEQ


__all__ = ["BeginMarkedContentSequenceWithProperties"]
