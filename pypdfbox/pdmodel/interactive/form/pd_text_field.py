from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos import COSDictionary, COSName, COSString

from .pd_variable_text import PDVariableText

if TYPE_CHECKING:
    from .pd_acro_form import PDAcroForm
    from .pd_non_terminal_field import PDNonTerminalField

_FT_KEY: COSName = COSName.get_pdf_name("FT")
_MAX_LEN: COSName = COSName.get_pdf_name("MaxLen")
_V: COSName = COSName.get_pdf_name("V")
_DV: COSName = COSName.get_pdf_name("DV")


class PDTextField(PDVariableText):
    """``/FT /Tx`` text field. Mirrors PDFBox ``PDTextField`` lite surface.

    Deferred upstream behavior: ``set_value`` does not regenerate the widget
    appearance stream nor handle rich-text DOM serialization to ``/RV``.
    """

    FT = "Tx"

    FLAG_MULTILINE = 1 << 12
    FLAG_PASSWORD = 1 << 13
    FLAG_FILE_SELECT = 1 << 20
    FLAG_DO_NOT_SPELL_CHECK = 1 << 22
    FLAG_DO_NOT_SCROLL = 1 << 23
    FLAG_COMB = 1 << 24
    FLAG_RICH_TEXT = 1 << 25

    def __init__(
        self,
        form: PDAcroForm,
        field: COSDictionary | None = None,
        parent: PDNonTerminalField | None = None,
    ) -> None:
        if field is None:
            field = COSDictionary()
            field.set_name(_FT_KEY, self.FT)
        super().__init__(form, field, parent)

    # ---------- flag accessors ----------

    def is_multiline(self) -> bool:
        return bool(self.get_field_flags() & self.FLAG_MULTILINE)

    def set_multiline(self, value: bool) -> None:
        self._set_flag(self.FLAG_MULTILINE, value)

    def is_password(self) -> bool:
        return bool(self.get_field_flags() & self.FLAG_PASSWORD)

    def set_password(self, value: bool) -> None:
        self._set_flag(self.FLAG_PASSWORD, value)

    def is_file_select(self) -> bool:
        return bool(self.get_field_flags() & self.FLAG_FILE_SELECT)

    def set_file_select(self, value: bool) -> None:
        self._set_flag(self.FLAG_FILE_SELECT, value)

    def is_do_not_spell_check(self) -> bool:
        return bool(self.get_field_flags() & self.FLAG_DO_NOT_SPELL_CHECK)

    def set_do_not_spell_check(self, value: bool) -> None:
        self._set_flag(self.FLAG_DO_NOT_SPELL_CHECK, value)

    def is_do_not_scroll(self) -> bool:
        return bool(self.get_field_flags() & self.FLAG_DO_NOT_SCROLL)

    def set_do_not_scroll(self, value: bool) -> None:
        self._set_flag(self.FLAG_DO_NOT_SCROLL, value)

    def is_comb(self) -> bool:
        return bool(self.get_field_flags() & self.FLAG_COMB)

    def set_comb(self, value: bool) -> None:
        self._set_flag(self.FLAG_COMB, value)

    def is_rich_text(self) -> bool:
        return bool(self.get_field_flags() & self.FLAG_RICH_TEXT)

    def set_rich_text(self, value: bool) -> None:
        self._set_flag(self.FLAG_RICH_TEXT, value)

    # ---------- /MaxLen ----------

    def get_max_len(self) -> int:
        return self._field.get_int(_MAX_LEN, -1)

    def set_max_len(self, max_len: int) -> None:
        self._field.set_int(_MAX_LEN, max_len)

    # ---------- /V, /DV ----------

    def get_value(self) -> str:
        item = self.get_inheritable_attribute(_V)
        if isinstance(item, COSString):
            return item.get_string()
        return ""

    def set_value(
        self, value: str | None, regenerate_appearance: bool = False
    ) -> None:
        """Set the field's ``/V`` value.

        When ``regenerate_appearance=True``, also rebuilds each widget's
        ``/AP /N`` normal appearance via :class:`PDAppearanceGenerator`.
        The default (``False``) preserves the historical lite-port behaviour
        of writing the value alone — the existing object graph is untouched
        for callers that flatten or re-render externally.
        """
        if value is None:
            self._field.remove_item(_V)
        else:
            self._field.set_string(_V, value)
        if regenerate_appearance:
            from .pd_appearance_generator import PDAppearanceGenerator

            PDAppearanceGenerator().generate(self)

    def get_default_value(self) -> str:
        item = self.get_inheritable_attribute(_DV)
        if isinstance(item, COSString):
            return item.get_string()
        return ""

    def set_default_value(self, value: str | None) -> None:
        if value is None:
            self._field.remove_item(_DV)
        else:
            self._field.set_string(_DV, value)

    def get_value_as_string(self) -> str:
        return self.get_value()


__all__ = ["PDTextField"]
