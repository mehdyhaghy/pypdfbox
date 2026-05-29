from __future__ import annotations

from pypdfbox.cos import COSBase, COSName
from pypdfbox.pdmodel.missing_resource_exception import MissingResourceException

from .. import MissingOperandException, Operator
from ..operator_processor import OperatorProcessor


class InvokeNamedXObject(OperatorProcessor):
    """``Do`` — Paint the form or image XObject referenced by the named
    resource. Mirrors
    ``org.apache.pdfbox.contentstream.operator.graphics.DrawObject``.

    Operand validation matches upstream:

    * Fewer than one operand raises :class:`MissingOperandException`
      (upstream throws the same exception type).
    * If the first operand is not a :class:`COSName`, the operator is
      silently skipped — mirrors upstream's early-return on the
      ``instanceof COSName`` guard.

    Resolution then mirrors upstream's type dispatch on the resolved
    ``PDXObject``:

    * an unresolved name raises :class:`MissingResourceException`;
    * an image XObject is forwarded to ``context.draw_image(image)``;
    * a transparency group is forwarded to
      ``context.show_transparency_group(group)``;
    * any other form XObject is forwarded to ``context.show_form(form)``.

    The graphics ``DrawObject`` (unlike the text-extraction one) does *not*
    short-circuit image XObjects — the whole point of
    :class:`~pypdfbox.contentstream.pdf_graphics_stream_engine.PDFGraphicsStreamEngine`
    is the ``draw_image`` hook, which tools such as ``ExtractImages`` and the
    renderer rely on. Recursion depth for nested forms is bounded inside
    ``show_form`` / the engine level counter, matching upstream.
    """

    OPERATOR_NAME = "Do"

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        if len(operands) < 1:
            raise MissingOperandException(operator, operands)
        base0 = operands[0]
        if not isinstance(base0, COSName):
            return
        name: COSName = base0

        context = self._context
        if context is None:
            return
        resources = context.get_resources()
        if resources is None:
            return

        xobject = resources.get_x_object(name)
        if xobject is None:
            raise MissingResourceException(f"Missing XObject: {name.get_name()}")

        if _is_image_xobject(xobject):
            context.draw_image(xobject)
        elif _is_transparency_group(xobject):
            context.show_transparency_group(xobject)
        elif _is_form_xobject(xobject):
            context.show_form(xobject)


def _is_image_xobject(obj: object) -> bool:
    return type(obj).__name__ == "PDImageXObject"


def _is_transparency_group(obj: object) -> bool:
    return type(obj).__name__ == "PDTransparencyGroup"


def _is_form_xobject(obj: object) -> bool:
    return type(obj).__name__ == "PDFormXObject" or getattr(
        obj, "is_form_xobject", False
    )
