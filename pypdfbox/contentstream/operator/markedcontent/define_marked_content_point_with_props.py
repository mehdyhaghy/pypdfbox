from __future__ import annotations

from pypdfbox.cos import COSBase, COSDictionary, COSName

from .. import Operator, OperatorName, OperatorProcessor


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
        tag: COSName | None = None
        if operands and isinstance(operands[0], COSName):
            tag = operands[0]
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
        if len(operands) < 2:
            return None
        prop = operands[1]
        if isinstance(prop, COSDictionary):
            return prop
        context = self._context
        if isinstance(prop, COSName) and context is not None:
            resources = None
            getter = getattr(context, "get_resources", None)
            if getter is not None:
                try:
                    resources = getter()
                except Exception:  # noqa: BLE001 — defensive
                    resources = None
            if resources is None:
                return None
            try:
                pl = resources.get_property_list(prop)
            except Exception:  # noqa: BLE001 — defensive: malformed dict
                return None
            if pl is None:
                return None
            try:
                return pl.get_cos_object()
            except Exception:  # noqa: BLE001 — defensive
                return None
        return None

    def get_name(self) -> str:
        return self.OPERATOR_NAME
