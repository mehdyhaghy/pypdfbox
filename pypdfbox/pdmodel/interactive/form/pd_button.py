from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSString

from .pd_terminal_field import PDTerminalField

if TYPE_CHECKING:
    from pypdfbox.pdmodel.interactive.annotation import PDAnnotationWidget

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
            string_value = item.name
            export_values = self.get_export_values()
            if export_values:
                # Mirror upstream: if /V parses as a non-negative integer
                # within the export-values range, return the matching export.
                # Otherwise fall through to returning the raw name string.
                try:
                    idx = int(string_value, 10)
                except ValueError:
                    return string_value
                if 0 <= idx < len(export_values):
                    return export_values[idx]
            return string_value
        if isinstance(item, COSString):
            return item.get_string()
        # Off is the default value when /V is not set. Per PDF spec.
        return "Off" if item is None else ""

    def set_value(self, value: str | None) -> None:
        """Set the selected option's name and update each widget's ``/AS``.

        Mirrors upstream ``PDButton.setValue(String)`` (PDButton.java 150):
        the value is validated through :meth:`check_value`, then dispatched
        into :meth:`update_by_option` when ``/Opt`` (export values) is set
        and :meth:`update_by_value` otherwise. Both helpers walk every
        widget's ``/AP /N`` subdictionary, install the matching appearance
        key as that widget's ``/AS``, and write the resolved ``/V`` to the
        field. Wave 1372 closed the divergence where ``set_value`` wrote
        only ``/V`` and left widget ``/AS`` stale.
        """
        if value is None:
            self._field.remove_item(_V)
            return
        self._check_value_if_known(value)
        if self.get_export_values():
            self.update_by_option(value)
        else:
            self.update_by_value(value)

    def has_value(self) -> bool:
        """Return ``True`` when this button has a parsable local ``/V`` value."""
        return isinstance(self._field.get_dictionary_object(_V), (COSName, COSString))

    def clear_value(self) -> None:
        """Remove this button's local ``/V`` entry."""
        self._field.remove_item(_V)

    def set_value_by_index(self, index: int) -> None:
        """Set the selected option by its index into ``/Opt``.

        Mirrors upstream ``PDButton.setValue(int)``: only usable when export
        values are present. Writes ``str(index)`` as the field's ``/V`` name
        — readers (including :meth:`get_value`) translate the integer-string
        back through the export-values list.

        :raises ValueError: if there are no export values, or ``index`` is
            outside ``0..len(export_values) - 1``.
        """
        export_values = self.get_export_values()
        if not export_values or index < 0 or index >= len(export_values):
            valid_upper = len(export_values) - 1
            raise ValueError(
                f"index '{index}' is not a valid index for the field "
                f"{self.get_fully_qualified_name()}, valid indices are from 0 "
                f"to {valid_upper}"
            )
        # Mirror upstream PDButton.setValue(int) (PDButton.java line 188):
        # this overload calls ``updateByValue`` directly with the
        # ``String.valueOf(index)`` token — bypassing the ``updateByOption``
        # dispatch ``setValue(String)`` would use when /Opt is present.
        self.update_by_value(str(index))

    def check_value(self, value: str) -> None:
        """Validate that ``value`` is a permitted on-state name or ``Off``.

        Mirrors upstream ``PDButton.checkValue``. Raises ``ValueError`` if
        the value is neither ``"Off"`` nor an entry in :meth:`get_on_values`.
        """
        on_values = self.get_on_values()
        if value != "Off" and value not in on_values:
            raise ValueError(
                f"value '{value}' is not a valid option for the field "
                f"{self.get_fully_qualified_name()}, valid values are: "
                f"{on_values} and Off"
            )

    def _check_value_if_known(self, value: str) -> None:
        """Validate button values when this field exposes known on-states.

        Sparse/fresh fields often lack widget appearances, so keep the legacy
        permissive path when no states are discoverable. If ``/Opt`` is present,
        also accept an integer-string index because :meth:`set_value_by_index`
        stores that representation.
        """
        on_values = self.get_on_values()
        if not on_values or value == "Off" or value in on_values:
            return
        export_values = self.get_export_values()
        if export_values:
            try:
                idx = int(value, 10)
            except ValueError:
                pass
            else:
                if 0 <= idx < len(export_values):
                    return
        raise ValueError(
            f"value '{value}' is not a valid option for the field "
            f"{self.get_fully_qualified_name()}, valid values are: "
            f"{on_values} and Off"
        )

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
            self._check_value_if_known(value)
            self._field.set_name(dv_key, value)

    def has_default_value(self) -> bool:
        """Return ``True`` when this button has a parsable local ``/DV`` value."""
        dv_key = COSName.get_pdf_name("DV")
        return isinstance(self._field.get_dictionary_object(dv_key), (COSName, COSString))

    def clear_default_value(self) -> None:
        """Remove this button's local ``/DV`` entry."""
        self._field.remove_item(COSName.get_pdf_name("DV"))

    def get_value_as_string(self) -> str:
        return self.get_value()

    # ---------- /Opt ----------

    def get_export_values(self) -> list[str]:
        item = self.get_inheritable_attribute(_OPT)
        if isinstance(item, COSString):
            # Upstream: ``Collections.singletonList(((COSString) value).getString())``.
            return [item.get_string()]
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

    def has_export_values(self) -> bool:
        """Return ``True`` when this button has a parsable local ``/Opt`` entry."""
        return isinstance(self._field.get_dictionary_object(_OPT), (COSArray, COSString))

    def clear_export_values(self) -> None:
        """Remove this button's local ``/Opt`` export-values entry."""
        self._field.remove_item(_OPT)

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
            on_value = self.get_on_value_for_widget(widget)
            if on_value:
                out.add(on_value)
        return out

    @staticmethod
    def get_on_value_for_widget(widget: PDAnnotationWidget) -> str:
        """Return the first non-``/Off`` key in this widget's ``/AP /N``
        subdictionary, or ``""`` if no normal-appearance subdictionary
        exists.

        Mirrors upstream private helper ``PDButton.getOnValueForWidget``
        (PDButton.java line 353).
        """
        cos = widget.get_cos_object()
        ap = cos.get_dictionary_object(COSName.get_pdf_name("AP"))
        if not isinstance(ap, COSDictionary):
            return ""
        n = ap.get_dictionary_object(COSName.get_pdf_name("N"))
        if not isinstance(n, COSDictionary):
            return ""
        off = COSName.get_pdf_name("Off")
        for key in n.key_set():
            if key != off:
                return key.name
        return ""

    def get_on_value_at_index(self, index: int) -> str:
        """Return the on-value of the widget at ``index``, or ``""``.

        Mirrors upstream private helper ``PDButton.getOnValue(int)``
        (PDButton.java line 340). Renamed in pypdfbox to disambiguate from
        :meth:`PDCheckBox.get_on_value` which is a different upstream
        overload (Java distinguishes by signature; Python cannot).
        """
        widgets = self.get_widgets()
        if index < len(widgets):
            return self.get_on_value_for_widget(widgets[index])
        return ""

    # Upstream private ``getOnValue(int)`` parity alias. Single-dispatch
    # forward to :meth:`get_on_value_at_index`. Subclasses such as
    # :class:`PDCheckBox` override ``get_on_value()`` (zero-arg) — the
    # subclass binding shadows this, which is fine because the parent only
    # uses :meth:`get_on_value_at_index` internally.
    def get_on_value(self, index: int) -> str:
        return self.get_on_value_at_index(index)

    def update_by_value(self, value: str) -> None:
        """Update each widget's ``/AS`` and the field's ``/V`` to ``value``.

        Mirrors upstream private helper ``PDButton.updateByValue``
        (PDButton.java line 391). Walks each widget's normal-appearance
        subdictionary, finds an entry matching ``value`` (handling encoding
        differences via :meth:`find_matching_appearance_key`), and sets
        ``/AS`` to that key — falling back to ``/Off`` per widget when no
        match. Writes ``/V`` to the first matched key, or to a fresh
        ``COSName(value)`` if no widget had a match.
        """
        matching_key: COSName | None = None

        for widget in self.get_widgets():
            cos = widget.get_cos_object()
            ap = cos.get_dictionary_object(COSName.get_pdf_name("AP"))
            if not isinstance(ap, COSDictionary):
                continue
            normal = ap.get_dictionary_object(COSName.get_pdf_name("N"))
            if not isinstance(normal, COSDictionary):
                continue

            widget_match = self.find_matching_appearance_key(normal, value)
            if widget_match is not None and matching_key is None:
                matching_key = widget_match

            if widget_match is not None:
                widget.set_appearance_state(widget_match.name)
            else:
                widget.set_appearance_state("Off")

        if matching_key is not None:
            self._field.set_item(_V, matching_key)
        else:
            self._field.set_name(_V, value)

    @staticmethod
    def find_matching_appearance_key(
        appearance_dict: COSDictionary, value: str
    ) -> COSName | None:
        """Return the appearance dictionary key whose decoded name equals
        ``value``, or ``None``.

        Mirrors upstream private helper
        ``PDButton.findMatchingAppearanceKey`` (PDButton.java line 452).
        Handles encoding differences between PDF-stored ISO-8859-1 keys
        and UTF-8 incoming values.
        """
        for key in appearance_dict.key_set():
            if isinstance(key, COSName) and key.name == value:
                return key
        return None

    def update_by_option(self, value: str) -> None:
        """Update appearance/value through the export-values (``/Opt``) path.

        Mirrors upstream private helper ``PDButton.updateByOption``
        (PDButton.java line 466). Requires the number of widgets to equal
        the number of options; ``"Off"`` short-circuits to the by-value
        path; otherwise the option's index becomes the on-value of the
        widget at that index.
        """
        widgets = self.get_widgets()
        options = self.get_export_values()

        if len(widgets) != len(options):
            raise ValueError(
                "The number of options doesn't match the number of widgets"
            )

        if value == "Off":
            self.update_by_value(value)
            return

        try:
            options_index = options.index(value)
        except ValueError:
            return
        on_value = self.get_on_value_at_index(options_index)
        self.update_by_value(on_value)

    def construct_appearances(self) -> None:
        """Sync widget appearance states against existing normal appearances.

        Mirrors upstream ``PDButton.constructAppearances``: it does not create
        missing appearance streams, it only sets each widget's ``/AS`` to the
        field ``/V`` when that state exists in ``/AP /N``; otherwise ``/Off``.
        """
        value = self.get_cos_object().get_dictionary_object(_V)
        if not isinstance(value, COSName):
            value = COSName.get_pdf_name("Off")
        off = COSName.get_pdf_name("Off")
        for widget in self.get_widgets():
            cos = widget.get_cos_object()
            ap = cos.get_dictionary_object(COSName.get_pdf_name("AP"))
            if not isinstance(ap, COSDictionary):
                continue
            normal = ap.get_dictionary_object(COSName.get_pdf_name("N"))
            if not isinstance(normal, COSDictionary):
                continue
            widget.set_appearance_state(value.name if normal.contains_key(value) else off.name)


__all__ = ["PDButton"]
