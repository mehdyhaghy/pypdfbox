from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos import COSArray, COSDictionary, COSName

from .pd_field import PDField

if TYPE_CHECKING:
    from .pd_acro_form import PDAcroForm
    from .pd_non_terminal_field import PDNonTerminalField

_KIDS: COSName = COSName.get_pdf_name("Kids")
_SUBTYPE: COSName = COSName.get_pdf_name("Subtype")


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

    def get_widgets(self) -> list[COSDictionary]:
        """Returns raw widget annotation dictionaries.

        Typed ``PDAnnotationWidget`` wrapping is deferred. If ``/Kids`` is
        absent the field itself acts as the widget (PDF spec — when a single
        widget is merged into the field dict).
        """
        kids = self._field.get_dictionary_object(_KIDS)
        if not isinstance(kids, COSArray):
            return [self._field]
        out: list[COSDictionary] = []
        for i in range(kids.size()):
            entry = kids.get_object(i)
            if isinstance(entry, COSDictionary):
                out.append(entry)
        return out


class PDFieldStub(PDTerminalField):
    """Generic concrete terminal field used until typed subclasses land."""


__all__ = ["PDTerminalField", "PDFieldStub"]
