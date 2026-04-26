from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos import COSBase, COSDictionary, COSName

if TYPE_CHECKING:
    from pypdfbox.pdmodel.interactive.action import PDFormFieldAdditionalActions

    from .pd_acro_form import PDAcroForm
    from .pd_non_terminal_field import PDNonTerminalField

_T: COSName = COSName.get_pdf_name("T")
_TU: COSName = COSName.get_pdf_name("TU")
_TM: COSName = COSName.get_pdf_name("TM")
_FT: COSName = COSName.get_pdf_name("FT")
_FF: COSName = COSName.get_pdf_name("Ff")
_AA: COSName = COSName.get_pdf_name("AA")
_PARENT: COSName = COSName.get_pdf_name("Parent")


class PDField:
    """Abstract base for AcroForm fields. Mirrors PDFBox ``PDField`` lite surface."""

    FLAG_READ_ONLY = 1
    FLAG_REQUIRED = 1 << 1
    FLAG_NO_EXPORT = 1 << 2

    def __init__(
        self,
        form: PDAcroForm,
        field: COSDictionary | None = None,
        parent: PDNonTerminalField | None = None,
    ) -> None:
        self._acro_form = form
        self._field = field if field is not None else COSDictionary()
        self._parent = parent

    # ---------- core ----------

    def get_cos_object(self) -> COSDictionary:
        return self._field

    def get_acro_form(self) -> PDAcroForm:
        return self._acro_form

    def get_parent(self) -> PDNonTerminalField | None:
        return self._parent

    def set_parent(self, parent: PDNonTerminalField | None) -> None:
        self._parent = parent
        if parent is None:
            self._field.remove_item(_PARENT)
        else:
            self._field.set_item(_PARENT, parent.get_cos_object())

    # ---------- /T, /TU, /TM ----------

    def get_partial_name(self) -> str | None:
        return self._field.get_string(_T)

    def set_partial_name(self, name: str | None) -> None:
        self._field.set_string(_T, name)

    def get_alternate_field_name(self) -> str | None:
        return self._field.get_string(_TU)

    def set_alternate_field_name(self, name: str | None) -> None:
        self._field.set_string(_TU, name)

    def get_mapping_name(self) -> str | None:
        return self._field.get_string(_TM)

    def set_mapping_name(self, name: str | None) -> None:
        self._field.set_string(_TM, name)

    # ---------- inheritable attribute walk ----------

    def get_inheritable_attribute(self, key: COSName) -> COSBase | None:
        """Walks self -> parent chain -> acroForm dictionary."""
        item = self._field.get_dictionary_object(key)
        if item is not None:
            return item
        if self._parent is not None:
            return self._parent.get_inheritable_attribute(key)
        return self._acro_form.get_cos_object().get_dictionary_object(key)

    def get_field_type(self) -> str | None:
        item = self.get_inheritable_attribute(_FT)
        if isinstance(item, COSName):
            return item.name
        return None

    def get_field_flags(self) -> int:
        item = self.get_inheritable_attribute(_FF)
        from pypdfbox.cos import COSInteger

        if isinstance(item, COSInteger):
            return item.value
        return 0

    def set_field_flags(self, flags: int) -> None:
        self._field.set_int(_FF, flags)

    # ---------- fully qualified name ----------

    def get_fully_qualified_name(self) -> str:
        partial = self.get_partial_name() or ""
        if self._parent is None:
            return partial
        parent_fqn = self._parent.get_fully_qualified_name()
        if not parent_fqn:
            return partial
        if not partial:
            return parent_fqn
        return f"{parent_fqn}.{partial}"

    # ---------- flag bit accessors ----------

    def _set_flag(self, mask: int, value: bool) -> None:
        flags = self.get_field_flags()
        if value:
            flags |= mask
        else:
            flags &= ~mask
        self.set_field_flags(flags)

    def is_read_only(self) -> bool:
        return bool(self.get_field_flags() & self.FLAG_READ_ONLY)

    def set_read_only(self, value: bool) -> None:
        self._set_flag(self.FLAG_READ_ONLY, value)

    def is_required(self) -> bool:
        return bool(self.get_field_flags() & self.FLAG_REQUIRED)

    def set_required(self, value: bool) -> None:
        self._set_flag(self.FLAG_REQUIRED, value)

    def is_no_export(self) -> bool:
        return bool(self.get_field_flags() & self.FLAG_NO_EXPORT)

    def set_no_export(self, value: bool) -> None:
        self._set_flag(self.FLAG_NO_EXPORT, value)

    # ---------- /AA (additional actions) ----------

    def get_actions(self) -> PDFormFieldAdditionalActions | None:
        from pypdfbox.pdmodel.interactive.action import PDFormFieldAdditionalActions

        value = self._field.get_dictionary_object(_AA)
        if isinstance(value, COSDictionary):
            return PDFormFieldAdditionalActions(value)
        return None

    def set_actions(
        self, aa: PDFormFieldAdditionalActions | COSDictionary | None
    ) -> None:
        if aa is None:
            self._field.remove_item(_AA)
            return
        self._field.set_item(
            _AA,
            aa.get_cos_object() if hasattr(aa, "get_cos_object") else aa,
        )

    # ---------- abstract ----------

    def is_terminal(self) -> bool:
        raise NotImplementedError


__all__ = ["PDField"]
