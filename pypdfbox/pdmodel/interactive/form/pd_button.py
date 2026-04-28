from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSString

from .pd_terminal_field import PDTerminalField

if TYPE_CHECKING:
    from .pd_acro_form import PDAcroForm
    from .pd_non_terminal_field import PDNonTerminalField

_FT_KEY: COSName = COSName.get_pdf_name("FT")
_V: COSName = COSName.get_pdf_name("V")
_OPT: COSName = COSName.get_pdf_name("Opt")


class PDButton(PDTerminalField):
    """Abstract intermediate ``/FT /Btn`` button. Mirrors PDFBox ``PDButton``
    lite surface.

    Concrete dispatch (push / radio / check) is performed by
    :class:`PDFieldFactory` based on the ``FLAG_PUSHBUTTON`` and ``FLAG_RADIO``
    bits.

    Deferred upstream behavior: ``get_on_values()`` returns an empty set in this
    scaffold (full implementation walks widget appearance dictionaries to
    collect the union of "on" state names).
    """

    FT = "Btn"

    FLAG_NO_TOGGLE_TO_OFF = 1 << 14
    FLAG_RADIO = 1 << 15
    FLAG_PUSHBUTTON = 1 << 16
    FLAG_RADIOS_IN_UNISON = 1 << 25

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

    # ---------- type bits ----------

    def is_push_button(self) -> bool:
        return bool(self.get_field_flags() & self.FLAG_PUSHBUTTON)

    def set_push_button(self, value: bool) -> None:
        self._set_flag(self.FLAG_PUSHBUTTON, value)
        if value and self.is_radio_button():
            self._set_flag(self.FLAG_RADIO, False)

    def is_radio_button(self) -> bool:
        return bool(self.get_field_flags() & self.FLAG_RADIO)

    def set_radio_button(self, value: bool) -> None:
        self._set_flag(self.FLAG_RADIO, value)
        if value and self.is_push_button():
            self._set_flag(self.FLAG_PUSHBUTTON, False)

    # ---------- /V ----------

    def get_value(self) -> str:
        item = self.get_inheritable_attribute(_V)
        if isinstance(item, COSName):
            return item.name
        if isinstance(item, COSString):
            return item.get_string()
        return ""

    def set_value(self, value: str | None) -> None:
        if value is None:
            self._field.remove_item(_V)
        else:
            self._field.set_name(_V, value)

    def get_default_value(self) -> str:
        dv_key = COSName.get_pdf_name("DV")
        item = self.get_inheritable_attribute(dv_key)
        if isinstance(item, COSName):
            return item.name
        if isinstance(item, COSString):
            return item.get_string()
        return ""

    def set_default_value(self, value: str | None) -> None:
        dv_key = COSName.get_pdf_name("DV")
        if value is None:
            self._field.remove_item(dv_key)
        else:
            self._field.set_name(dv_key, value)

    def get_value_as_string(self) -> str:
        return self.get_value()

    # ---------- /Opt ----------

    def get_export_values(self) -> list[str]:
        item = self._field.get_dictionary_object(_OPT)
        if not isinstance(item, COSArray):
            return []
        out: list[str] = []
        for i in range(item.size()):
            entry = item.get_object(i)
            if isinstance(entry, COSString):
                out.append(entry.get_string())
            elif isinstance(entry, COSName):
                out.append(entry.name)
        return out

    def set_export_values(self, values: list[str] | None) -> None:
        if not values:
            self._field.remove_item(_OPT)
            return
        arr = COSArray.of_cos_strings(values)
        self._field.set_item(_OPT, arr)

    def get_on_values(self) -> set[str]:
        """Returns the union of widget appearance "on" state names.

        Mirrors upstream ``PDButton.getOnValues``:
        - If ``/Opt`` is non-empty, returns its entries (preserving order
          via ``LinkedHashSet`` upstream — we use a list-backed dedupe).
        - Otherwise walks each widget's ``/AP /N`` subdictionary and
          collects the first non-``/Off`` name.

        Returns a Python ``set`` (membership semantics match upstream
        callers like :meth:`PDRadioButton.get_selected_export_values`).
        """
        export_values = self.get_export_values()
        if export_values:
            # preserve insertion order while dedup'ing
            seen: list[str] = []
            for value in export_values:
                if value not in seen:
                    seen.append(value)
            return set(seen)
        out: set[str] = set()
        for widget in self.get_widgets():
            on_value = self._on_value_for_widget(widget)
            if on_value is not None:
                out.add(on_value)
        return out

    @staticmethod
    def _on_value_for_widget(widget) -> str | None:
        """Return the first non-``/Off`` key in this widget's ``/AP /N``
        subdictionary, or ``None`` if no normal-appearance subdictionary
        exists. Used by :meth:`get_on_values`."""
        cos = widget.get_cos_object()
        ap = cos.get_dictionary_object(COSName.get_pdf_name("AP"))
        if not isinstance(ap, COSDictionary):
            return None
        n = ap.get_dictionary_object(COSName.get_pdf_name("N"))
        if not isinstance(n, COSDictionary):
            return None
        off = COSName.get_pdf_name("Off")
        for key in n.key_set():
            if key != off:
                return key.name
        return None


__all__ = ["PDButton"]
