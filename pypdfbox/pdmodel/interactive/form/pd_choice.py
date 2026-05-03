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

    Deferred upstream behavior: appearance regeneration is not performed by
    this base class.
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

    def has_options(self) -> bool:
        """Predicate — return ``True`` when ``/Opt`` is set on this field's own
        dictionary.

        Pypdfbox-only convenience: lets callers distinguish "explicit empty
        ``/Opt``" from "no ``/Opt`` entry" without rereading the dict directly.
        :meth:`get_options` returns ``[]`` for both cases.
        """
        return self._field.contains_key(_OPT)

    def get_options(self) -> list[str]:
        """Returns the export half of /Opt entries (or the value itself when
        an entry is a single string), matching upstream ``PDChoice.getOptions``.

        Mirrors upstream ``FieldUtils.getPairableItems`` semantics: when
        ``/Opt`` is itself a ``COSString`` (technically out-of-spec but
        observed in the wild), the value is wrapped in a singleton list
        rather than dropped.
        """
        opt = self._field.get_dictionary_object(_OPT)
        if isinstance(opt, COSString):
            return [opt.get_string()]
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

    def set_options(
        self,
        values: list[str] | None,
        display_values: list[str] | None = None,
    ) -> None:
        """Set the field's ``/Opt`` entries.

        Single-argument call mirrors upstream ``setOptions(List<String>)`` and
        writes a flat ``COSArray`` of strings (sorted when ``is_sort()`` is
        true, per upstream).

        Two-argument call mirrors upstream
        ``setOptions(List<String> exportValues, List<String> displayValues)``
        — writes ``[export, display]`` two-element ``COSArray`` pairs. Sizes
        must match. Sorting (when ``is_sort()`` is true) preserves the
        export/display pairing by sorting on the display half.
        """
        if display_values is None:
            # single-arg / display-only form
            if not values:
                self._field.remove_item(_OPT)
                return
            ordered = sorted(values) if self.is_sort() else list(values)
            arr = COSArray.of_cos_strings(ordered)
            self._field.set_item(_OPT, arr)
            return

        # two-arg form: values is the export list
        export_values = values
        if not export_values or not display_values:
            self._field.remove_item(_OPT)
            return
        if len(export_values) != len(display_values):
            raise ValueError(
                "The number of export values must match the number of display values"
            )
        pairs = list(zip(export_values, display_values, strict=True))
        if self.is_sort():
            pairs.sort(key=lambda kv: kv[1])
        options = COSArray()
        for export, display in pairs:
            entry = COSArray()
            entry.add(COSString(export))
            entry.add(COSString(display))
            options.add(entry)
        self._field.set_item(_OPT, options)

    def has_separate_export_and_display_values(self) -> bool:
        """Mirrors upstream ``PDChoice.hasSeparateExportAndDisplayValues``."""
        return self.get_options_export_values() != self.get_options_display_values()

    def get_options_export_values(self) -> list[str]:
        # Upstream ``getOptionsExportValues`` returns getOptions() when entries
        # are single strings, and the export half (first of pair) otherwise —
        # which is exactly ``get_options`` above.
        return self.get_options()

    def get_options_display_values(self) -> list[str]:
        """Returns the display half of /Opt entries (or the value itself when
        an entry is a single string), matching upstream
        ``PDChoice.getOptionsDisplayValues``.

        Mirrors upstream ``FieldUtils.getPairableItems`` semantics: when
        ``/Opt`` is itself a ``COSString`` (technically out-of-spec but
        observed in the wild), the value is wrapped in a singleton list
        rather than dropped.
        """
        opt = self._field.get_dictionary_object(_OPT)
        if isinstance(opt, COSString):
            return [opt.get_string()]
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

    def _selected_option_indices_for_values(self, values: list[str]) -> list[int]:
        options = self.get_options_export_values()
        if not options:
            return []
        indices: list[int] = []
        for value in values:
            try:
                indices.append(options.index(value))
            except ValueError as exc:
                if self.is_combo() and bool(getattr(self, "is_edit", lambda: False)()):
                    return []
                raise ValueError(f"value {value!r} is not one of the field options") from exc
        # PDF 32000-1 §12.7.4.4: /I "shall be sorted in ascending order".
        # Upstream PDChoice.updateSelectedOptionsIndex calls Collections.sort.
        indices.sort()
        return indices

    def _normalize_value_for_set(self, value: list[str] | str) -> list[str]:
        values = [value] if isinstance(value, str) else list(value)
        if len(values) > 1 and not self.is_multi_select():
            raise ValueError("multiple values are only allowed for multi-select choice fields")
        indices = self._selected_option_indices_for_values(values)
        if indices:
            self.set_selected_options_indices(indices)
        else:
            self.set_selected_options_indices(None)
        return values

    def get_value(self) -> list[str]:
        item = self.get_inheritable_attribute(_V)
        return self._read_string_or_array(item)

    def set_value(self, value: list[str] | str | None) -> None:
        if value is None:
            self._field.remove_item(_V)
            self.set_selected_options_indices(None)
            return
        values = self._normalize_value_for_set(value)
        # Mirrors upstream PDChoice.setValue(List): an empty list clears both
        # /V and /I rather than writing an empty COSArray.
        if not values:
            self._field.remove_item(_V)
            self.set_selected_options_indices(None)
            return
        cos = self._write_string_or_array(values)
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

    # Upstream PDFBox names (singular). Aliases for the plural pythonic forms.
    def get_selected_options_index(self) -> list[int]:
        """Upstream PDFBox name (``getSelectedOptionsIndex``). Alias for
        :meth:`get_selected_options_indices`."""
        return self.get_selected_options_indices()

    def set_selected_options_index(self, indices: list[int] | None) -> None:
        """Upstream PDFBox name (``setSelectedOptionsIndex``). Alias for
        :meth:`set_selected_options_indices`."""
        self.set_selected_options_indices(indices)


__all__ = ["PDChoice"]
