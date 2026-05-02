from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos import COSDictionary, COSName

from .pd_button import PDButton

if TYPE_CHECKING:
    from .pd_acro_form import PDAcroForm
    from .pd_non_terminal_field import PDNonTerminalField

_FT_KEY: COSName = COSName.get_pdf_name("FT")


class PDRadioButton(PDButton):
    """``/FT /Btn`` with ``FLAG_RADIO`` set. Mirrors PDFBox ``PDRadioButton``."""

    def __init__(
        self,
        form: PDAcroForm,
        field: COSDictionary | None = None,
        parent: PDNonTerminalField | None = None,
    ) -> None:
        new_field = field is None
        if new_field:
            field = COSDictionary()
            field.set_name(_FT_KEY, self.FT)
        super().__init__(form, field, parent)
        if new_field:
            self.set_field_flags(self.FLAG_RADIO)

    def is_radios_in_unison(self) -> bool:
        return bool(self.get_field_flags() & self.FLAG_RADIOS_IN_UNISON)

    def set_radios_in_unison(self, value: bool) -> None:
        self._set_flag(self.FLAG_RADIOS_IN_UNISON, value)

    def is_no_toggle_to_off(self) -> bool:
        """Whether the ``NoToggleToOff`` ``/Ff`` bit is set.

        Per PDF 32000-1 §12.7.4.2.1, when this bit is set exactly one radio
        button shall be selected at all times — selecting the currently
        selected button has no effect (cannot toggle the group "off").
        Mirrors the upstream ``FLAG_NO_TOGGLE_TO_OFF`` bit (1 << 14) which
        upstream ``PDRadioButton`` declares but does not currently expose.
        """
        return bool(self.get_field_flags() & self.FLAG_NO_TOGGLE_TO_OFF)

    def set_no_toggle_to_off(self, value: bool) -> None:
        """Toggle the ``NoToggleToOff`` ``/Ff`` bit. See :meth:`is_no_toggle_to_off`."""
        self._set_flag(self.FLAG_NO_TOGGLE_TO_OFF, value)

    # ---------- selection accessors ----------

    def get_selected_index(self) -> int:
        """Index of the currently selected widget, or -1 if none.

        Mirrors upstream ``PDRadioButton.getSelectedIndex``: walks the
        widget list and returns the index of the first widget whose
        ``/AS`` is not ``/Off``.
        """
        for idx, widget in enumerate(self.get_widgets()):
            if widget.get_appearance_state() != "Off":
                return idx
        return -1

    def get_selected_export_values(self) -> list[str]:
        """Selected widget's export values (per ``/Opt``).

        Mirrors upstream ``PDRadioButton.getSelectedExportValues``:
        - When ``/Opt`` is empty, returns ``[get_value()]``.
        - Otherwise returns the export-values entries whose corresponding
          widget on-state matches ``get_value()``.

        Note: upstream iterates ``getOnValues()`` (a ``LinkedHashSet`` with
        insertion order) parallel to ``exportValues``. We iterate
        ``export_values`` directly for index correspondence — ``get_on_values``
        on this port returns a Python ``set`` whose iteration order is not
        guaranteed.
        """
        export_values = self.get_export_values()
        if not export_values:
            return [self.get_value()]
        selected: list[str] = []
        field_value = self.get_value()
        for idx, on_value in enumerate(export_values):
            if on_value == field_value:
                selected.append(export_values[idx])
        return selected

    # ---------- /V + appearance ----------

    def set_value(
        self, value: str | None, regenerate_appearance: bool = False
    ) -> None:
        """Set the field's ``/V`` value.

        When ``regenerate_appearance=True``, also rebuilds each widget's
        ``/AP /N`` two-state on/off appearance subdictionary via
        :class:`PDAppearanceGenerator` (radio kids draw a filled circle
        on the on-state) and syncs ``/AS`` per widget. The default
        (``False``) preserves the historical lite-port behaviour of
        writing the value alone.
        """
        super().set_value(value)
        if regenerate_appearance:
            from .pd_appearance_generator import PDAppearanceGenerator

            PDAppearanceGenerator().generate(self)

    def construct_appearances(self) -> None:
        super().construct_appearances()


__all__ = ["PDRadioButton"]
