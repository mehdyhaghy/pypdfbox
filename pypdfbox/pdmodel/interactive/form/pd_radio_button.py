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

        The base :meth:`PDButton.set_value` already performs the
        value-visible appearance step for radio groups — it syncs each
        widget's ``/AS`` to the matching existing ``/AP /N`` on-state (or
        ``/Off``), which is what upstream ``PDRadioButton.setValue`` does
        (real radio widgets ship their on/off streams; setting the value
        only flips ``/AS``). ``regenerate_appearance`` therefore defaults to
        ``False``: pass ``True`` only to additionally *redraw* the on/off
        appearance streams (filled circle on the on-state) via
        :class:`PDAppearanceGenerator`. Redrawing is opt-in because it
        rebuilds the ``/AP /N`` subdictionary from scratch and would discard
        producer-chosen state keys (e.g. the numeric ``/Opt``-indexed keys in
        PDFBOX-3656).

        Ordering note (wave 1487): like :meth:`PDCheckBox.set_value`, when
        ``regenerate_appearance`` is set the appearance streams are rebuilt
        *before* the base :meth:`PDButton.set_value` runs its strict
        :meth:`PDButton.check_value`, so a freshly built AP-less group (whose
        on-values would otherwise be ``{""}``) gets its ``/AP /N`` on-states
        installed first and ``value`` becomes a recognised on-value.
        """
        if regenerate_appearance:
            from .pd_appearance_generator import PDAppearanceGenerator

            PDAppearanceGenerator().generate(self)
        super().set_value(value)

    def construct_appearances(self) -> None:
        """Rebuild widget appearances for this radio button group.

        Wave 1305: like :meth:`PDCheckBox.construct_appearances`, the
        appearance generator is invoked so every widget kid gets a
        fresh on/off ``/AP /N`` subdictionary (the on-state draws a
        filled circle), then the super call syncs each widget's
        ``/AS`` against the rebuilt appearance dictionary. Mirrors the
        user-visible contract of upstream's ``AppearanceGeneratorHelper``
        flow while preserving ``PDButton.constructAppearances``'s
        state-sync semantics.
        """
        from .pd_appearance_generator import PDAppearanceGenerator

        PDAppearanceGenerator().generate(self)
        super().construct_appearances()


__all__ = ["PDRadioButton"]
