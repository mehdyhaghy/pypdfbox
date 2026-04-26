from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos import COSArray, COSBase, COSDictionary, COSName

from .pd_field import PDField

if TYPE_CHECKING:
    from .pd_acro_form import PDAcroForm

_KIDS: COSName = COSName.get_pdf_name("Kids")
_V: COSName = COSName.get_pdf_name("V")


class PDNonTerminalField(PDField):
    """Non-terminal field — a node whose descendants are fields. Mirrors PDFBox ``PDNonTerminalField``."""

    def __init__(
        self,
        form: PDAcroForm,
        field: COSDictionary | None = None,
        parent: PDNonTerminalField | None = None,
    ) -> None:
        super().__init__(form, field, parent)

    def is_terminal(self) -> bool:
        return False

    def get_children(self) -> list[PDField]:
        from .pd_field_factory import PDFieldFactory

        kids = self._field.get_dictionary_object(_KIDS)
        if not isinstance(kids, COSArray):
            return []
        out: list[PDField] = []
        parent_dict = self._field
        for i in range(kids.size()):
            entry = kids.get_object(i)
            if not isinstance(entry, COSDictionary):
                continue
            if entry is parent_dict:
                # self-reference guard, mirrors upstream
                continue
            child = PDFieldFactory.create_field(self._acro_form, entry, self)
            if child is not None:
                out.append(child)
        return out

    def set_children(self, children: list[PDField]) -> None:
        kids = COSArray()
        for child in children:
            child.set_parent(self)
            kids.add(child.get_cos_object())
        self._field.set_item(_KIDS, kids)

    # ---------- /V (raw COSBase per upstream) ----------

    def get_value(self) -> COSBase | None:
        """Returns the raw ``/V`` entry on this node. Mirrors upstream
        ``PDNonTerminalField.getValue`` which returns ``COSBase``.

        Per PDF 32000-1 §12.7.4 children inherit ``/V`` from their parent when
        their own ``/V`` is absent — that walk is performed lazily on each
        child via :meth:`PDField.get_inheritable_attribute`. This method does
        not eagerly resolve children's effective values.
        """
        return self._field.get_dictionary_object(_V)

    def set_value(self, value: COSBase | None) -> None:
        if value is None:
            self._field.remove_item(_V)
        else:
            self._field.set_item(_V, value)

    def get_value_as_string(self) -> str:
        """String view of own ``/V`` if it carries a single primitive value,
        else the empty string. Mirrors upstream
        ``PDNonTerminalField.getValueAsString``.
        """
        from pypdfbox.cos import COSString

        item = self.get_value()
        if isinstance(item, COSString):
            return item.get_string()
        if isinstance(item, COSName):
            return item.name
        return ""


__all__ = ["PDNonTerminalField"]
