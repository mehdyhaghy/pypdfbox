"""``DP`` — Define a marked-content point with properties.

Mirrors ``org.apache.pdfbox.contentstream.operator.markedcontent.MarkedContentPointWithProperties``
(PDFBox 3.x; Java path
``pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/markedcontent/MarkedContentPointWithProperties.java``).
"""

from __future__ import annotations

from pypdfbox.cos import COSBase, COSDictionary, COSName

from .. import MissingOperandException, Operator, OperatorName, OperatorProcessor


class MarkedContentPointWithProperties(OperatorProcessor):
    """``DP`` — flag a single point in the content stream as a marked
    content point with an associated property dictionary."""

    OPERATOR_NAME = OperatorName.MARKED_CONTENT_POINT_WITH_PROPS

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
        hook = getattr(context, "marked_content_point", None)
        if hook is not None:
            hook(tag, prop_dict)

    def get_name(self) -> str:
        return OperatorName.MARKED_CONTENT_POINT_WITH_PROPS


__all__ = ["MarkedContentPointWithProperties"]
