from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.pdmodel.interactive.annotation import PDAnnotationWidget

from .pd_field import PDField

if TYPE_CHECKING:
    from pypdfbox.pdmodel.interactive.action import PDFormFieldAdditionalActions

    from .pd_acro_form import PDAcroForm
    from .pd_non_terminal_field import PDNonTerminalField

_logger = logging.getLogger(__name__)

_KIDS: COSName = COSName.get_pdf_name("Kids")
_AA: COSName = COSName.get_pdf_name("AA")


class PDTerminalField(PDField):
    """Leaf field base. Mirrors PDFBox ``PDTerminalField`` lite surface."""

    def __init__(
        self,
        form: PDAcroForm,
        field: COSDictionary | None = None,
        parent: PDNonTerminalField | None = None,
    ) -> None:
        super().__init__(form, field, parent)

    def is_terminal(self) -> bool:
        return True

    # ---------- /AA (additional actions) ----------

    def set_actions(self, actions: PDFormFieldAdditionalActions | None) -> None:
        """Set ``/AA`` form-field additional actions.

        Mirrors upstream ``PDTerminalField.setActions(PDFormFieldAdditionalActions)``
        — the narrower typed override over :meth:`PDField.set_actions`.
        """
        if actions is None:
            self._field.remove_item(_AA)
            return
        self._field.set_item(_AA, actions.get_cos_object())

    # ---------- widgets (/Kids) ----------

    def get_widgets(self) -> list[PDAnnotationWidget]:
        """Returns typed widget annotations.

        When ``/Kids`` is absent the field itself acts as the widget (PDF
        spec — single-widget shortcut where the widget dictionary is merged
        into the field dictionary), so a single :class:`PDAnnotationWidget`
        wrapping ``self._field`` is returned.
        """
        kids = self._field.get_dictionary_object(_KIDS)
        if not isinstance(kids, COSArray):
            return [PDAnnotationWidget(self._field)]
        out: list[PDAnnotationWidget] = []
        for i in range(kids.size()):
            entry = kids.get_object(i)
            if isinstance(entry, COSDictionary):
                out.append(PDAnnotationWidget(entry))
        return out

    def set_widgets(self, widgets: list[PDAnnotationWidget]) -> None:
        """Replace ``/Kids`` with the supplied widget annotations.

        Each widget's ``/Parent`` is wired back at this field. Lite version:
        always writes a ``/Kids`` array even for a single widget. Upstream's
        single-widget merge optimisation (where the lone widget dictionary
        is folded into the field dictionary) is deferred — we keep the
        explicit ``/Kids`` form so the object graph stays predictable.
        """
        kids = COSArray()
        for w in widgets:
            cos = w.get_cos_object()
            cos.set_item(COSName.get_pdf_name("Parent"), self._field)
            kids.add(cos)
        self._field.set_item(_KIDS, kids)

    # ---------- appearance ----------

    def apply_change(self) -> None:
        """No-op on the lite surface.

        Upstream triggers appearance regeneration (``PDAppearanceGenerator``)
        when the field's value or geometry changes. Appearance regeneration
        is deferred — see ``CHANGES.md``.
        """
        _logger.debug(
            "PDTerminalField.apply_change: appearance regeneration deferred"
        )

    def construct_appearances(self) -> None:
        """No-op on the lite surface.

        Upstream rebuilds the ``/AP`` appearance streams for every widget of
        this field via ``PDAppearanceGenerator``. Deferred — see
        ``CHANGES.md``.
        """
        _logger.debug(
            "PDTerminalField.construct_appearances: appearance regeneration deferred"
        )


class PDFieldStub(PDTerminalField):
    """Generic concrete terminal field used until typed subclasses land."""


__all__ = ["PDTerminalField", "PDFieldStub"]
