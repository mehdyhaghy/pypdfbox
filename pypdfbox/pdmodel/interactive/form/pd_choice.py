from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName, COSString

from .pd_variable_text import PDVariableText

if TYPE_CHECKING:
    from .pd_acro_form import PDAcroForm
    from .pd_non_terminal_field import PDNonTerminalField

_FT_KEY: COSName = COSName.get_pdf_name("FT")
_OPT: COSName = COSName.get_pdf_name("Opt")
_TI: COSName = COSName.get_pdf_name("TI")
_V: COSName = COSName.get_pdf_name("V")
_DV: COSName = COSName.get_pdf_name("DV")
_I: COSName = COSName.get_pdf_name("I")


def _entry_to_str(entry) -> str | None:
    if isinstance(entry, COSString):
        return entry.get_string()
    if isinstance(entry, COSName):
        return entry.name
    return None


class PDChoice(PDVariableText):
    """Abstract intermediate ``/FT /Ch`` choice field. Mirrors PDFBox
    ``PDChoice`` lite surface.

    Concrete dispatch (combo / list) is done by :class:`PDFieldFactory` based
    on the ``FLAG_COMBO`` bit.

    Deferred upstream behavior: ``set_value(list)`` does not validate against
    available options; appearance regeneration is not performed.
    """

    FT = "Ch"

    FLAG_COMBO = 1 << 17
    FLAG_EDIT = 1 << 18
    FLAG_SORT = 1 << 19
    FLAG_MULTI_SELECT = 1 << 21
    FLAG_DO_NOT_SPELL_CHECK = 1 << 22
    FLAG_COMMIT_ON_SEL_CHANGE = 1 << 26

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

    def is_combo(self) -> bool:
        return bool(self.get_field_flags() & self.FLAG_COMBO)

    def set_combo(self, value: bool) -> None:
        self._set_flag(self.FLAG_COMBO, value)

    def is_sort(self) -> bool:
        return bool(self.get_field_flags() & self.FLAG_SORT)

    def set_sort(self, value: bool) -> None:
        self._set_flag(self.FLAG_SORT, value)

    def is_multi_select(self) -> bool:
        return bool(self.get_field_flags() & self.FLAG_MULTI_SELECT)

    def set_multi_select(self, value: bool) -> None:
        self._set_flag(self.FLAG_MULTI_SELECT, value)

    def is_do_not_spell_check(self) -> bool:
        return bool(self.get_field_flags() & self.FLAG_DO_NOT_SPELL_CHECK)

    def set_do_not_spell_check(self, value: bool) -> None:
        self._set_flag(self.FLAG_DO_NOT_SPELL_CHECK, value)

    def is_commit_on_sel_change(self) -> bool:
        return bool(self.get_field_flags() & self.FLAG_COMMIT_ON_SEL_CHANGE)

    def set_commit_on_sel_change(self, value: bool) -> None:
        self._set_flag(self.FLAG_COMMIT_ON_SEL_CHANGE, value)

    # ---------- /Opt ----------

    def get_options(self) -> list[str]:
        """Returns the export half of /Opt entries (or the value itself when
        an entry is a single string), matching upstream ``PDChoice.getOptions``.
        """
        opt = self._field.get_dictionary_object(_OPT)
        if not isinstance(opt, COSArray):
            return []
        out: list[str] = []
        for i in range(opt.size()):
            entry = opt.get_object(i)
            if isinstance(entry, COSArray) and entry.size() > 0:
                first = entry.get_object(0)
                value = _entry_to_str(first)
                if value is not None:
                    out.append(value)
            else:
                value = _entry_to_str(entry)
                if value is not None:
                    out.append(value)
        return out

    def set_options(self, values: list[str] | None) -> None:
        if not values:
            self._field.remove_item(_OPT)
            return
        ordered = sorted(values) if self.is_sort() else list(values)
        arr = COSArray.of_cos_strings(ordered)
        self._field.set_item(_OPT, arr)

    def get_options_export_values(self) -> list[str]:
        # Upstream ``getOptionsExportValues`` returns getOptions() when entries
        # are single strings, and the export half (first of pair) otherwise —
        # which is exactly ``get_options`` above.
        return self.get_options()

    def get_options_display_values(self) -> list[str]:
        opt = self._field.get_dictionary_object(_OPT)
        if not isinstance(opt, COSArray):
            return []
        out: list[str] = []
        for i in range(opt.size()):
            entry = opt.get_object(i)
            if isinstance(entry, COSArray) and entry.size() > 1:
                second = entry.get_object(1)
                value = _entry_to_str(second)
                if value is not None:
                    out.append(value)
            else:
                value = _entry_to_str(entry)
                if value is not None:
                    out.append(value)
        return out

    # ---------- /TI ----------

    def get_top_index(self) -> int:
        return self._field.get_int(_TI, 0)

    def set_top_index(self, top: int | None) -> None:
        if top is None:
            self._field.remove_item(_TI)
        else:
            self._field.set_int(_TI, top)

    # ---------- /V, /DV ----------

    @staticmethod
    def _read_string_or_array(item) -> list[str]:
        if item is None:
            return []
        if isinstance(item, COSString):
            return [item.get_string()]
        if isinstance(item, COSName):
            return [item.name]
        if isinstance(item, COSArray):
            out: list[str] = []
            for i in range(item.size()):
                value = _entry_to_str(item.get_object(i))
                if value is not None:
                    out.append(value)
            return out
        return []

    @staticmethod
    def _write_string_or_array(values: list[str] | str | None):
        if values is None:
            return None
        if isinstance(values, str):
            return COSString(values)
        if len(values) == 1:
            return COSString(values[0])
        return COSArray.of_cos_strings(values)

    def get_value(self) -> list[str]:
        item = self.get_inheritable_attribute(_V)
        return self._read_string_or_array(item)

    def set_value(self, value: list[str] | str | None) -> None:
        if value is None:
            self._field.remove_item(_V)
            return
        cos = self._write_string_or_array(value)
        self._field.set_item(_V, cos)

    def get_value_as_string(self) -> str:
        """Comma-joined view of ``get_value`` — mirrors PDFBox
        ``PDChoice.getValueAsString``.
        """
        values = self.get_value()
        return ",".join(values)

    def get_default_value(self) -> list[str]:
        item = self.get_inheritable_attribute(_DV)
        return self._read_string_or_array(item)

    def set_default_value(self, value: list[str] | str | None) -> None:
        if value is None:
            self._field.remove_item(_DV)
            return
        cos = self._write_string_or_array(value)
        self._field.set_item(_DV, cos)

    # ---------- /I ----------

    def get_selected_options_indices(self) -> list[int]:
        item = self._field.get_dictionary_object(_I)
        if not isinstance(item, COSArray):
            return []
        out: list[int] = []
        for i in range(item.size()):
            entry = item.get_object(i)
            if isinstance(entry, COSInteger):
                out.append(entry.value)
        return out

    def set_selected_options_indices(self, indices: list[int] | None) -> None:
        if not indices:
            self._field.remove_item(_I)
            return
        self._field.set_item(_I, COSArray.of_cos_integers(indices))


__all__ = ["PDChoice"]
