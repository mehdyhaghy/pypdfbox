from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos import COSArray, COSBase, COSDictionary, COSInteger, COSName

from .pd_field import PDField

if TYPE_CHECKING:
    from pypdfbox.pdmodel.interactive.annotation import PDAnnotationWidget

    from .pd_acro_form import PDAcroForm

_KIDS: COSName = COSName.get_pdf_name("Kids")
_V: COSName = COSName.get_pdf_name("V")
_DV: COSName = COSName.get_pdf_name("DV")
_FT: COSName = COSName.get_pdf_name("FT")
_FF: COSName = COSName.get_pdf_name("Ff")


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

    # ---------- /DV (raw COSBase per upstream) ----------

    def get_default_value(self) -> COSBase | None:
        """Returns the raw ``/DV`` entry on this node. Mirrors upstream
        ``PDNonTerminalField.getDefaultValue`` which returns ``COSBase``.

        Like :meth:`get_value`, this returns the local value without walking
        the inheritance chain. Per PDF 32000-1 §12.7.4 children inherit
        ``/DV`` lazily via :meth:`PDField.get_inheritable_attribute`.
        """
        return self._field.get_dictionary_object(_DV)

    def set_default_value(self, value: COSBase | None) -> None:
        if value is None:
            self._field.remove_item(_DV)
        else:
            self._field.set_item(_DV, value)

    # ---------- non-inherited /FT, /Ff overrides ----------

    def get_field_type(self) -> str | None:
        """Returns the local ``/FT`` entry without walking the parent chain.

        Mirrors upstream ``PDNonTerminalField.getFieldType`` — non-terminal
        fields carry ``/FT`` as an inheritable attribute for their descendants
        but the type does not logically belong to the non-terminal node itself.
        """
        item = self._field.get_dictionary_object(_FT)
        if isinstance(item, COSName):
            return item.name
        return None

    def get_field_flags(self) -> int:
        """Returns the local ``/Ff`` entry without walking the parent chain.

        Mirrors upstream ``PDNonTerminalField.getFieldFlags`` — there is no
        need to walk up since ``/Ff`` is inherited by descendants, not by this
        node itself.
        """
        item = self._field.get_dictionary_object(_FF)
        if isinstance(item, COSInteger):
            return item.value
        return 0

    # ---------- widgets ----------

    def get_widgets(self) -> list[PDAnnotationWidget]:
        """Non-terminal fields have no widgets — always returns an empty list.

        Mirrors upstream ``PDNonTerminalField.getWidgets`` which returns
        ``Collections.emptyList()``.
        """
        return []


__all__ = ["PDNonTerminalField"]
