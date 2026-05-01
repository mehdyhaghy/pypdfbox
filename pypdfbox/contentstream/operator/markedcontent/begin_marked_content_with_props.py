from __future__ import annotations

from pypdfbox.cos import COSBase, COSDictionary, COSName

from .. import Operator, OperatorName, OperatorProcessor


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

    Forwards ``(tag, properties)`` to the engine's
    :meth:`begin_marked_content_sequence` hook when the engine exposes
    one. ``properties`` may be ``None`` if the named property list cannot
    be resolved or the operands are malformed.
    """

    OPERATOR_NAME = OperatorName.BEGIN_MARKED_CONTENT_SEQ  # "BDC"

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        del operator  # unused — operator name fixed by registration
        tag: COSName | None = None
        if operands and isinstance(operands[0], COSName):
            tag = operands[0]
        properties = self._resolve_properties(operands)
        context = self._context
        if context is None:
            return
        hook = getattr(context, "begin_marked_content_sequence", None)
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

    @property
    def name(self) -> str:
        """Pythonic accessor mirroring :class:`Operator.name`. Returns
        the same token as :meth:`get_name`."""
        return self.OPERATOR_NAME
