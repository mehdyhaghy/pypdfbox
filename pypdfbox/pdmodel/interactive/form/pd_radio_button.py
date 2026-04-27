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


__all__ = ["PDRadioButton"]
