from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos import COSDictionary, COSName

from .pd_button import PDButton

if TYPE_CHECKING:
    from collections.abc import KeysView

    from .pd_acro_form import PDAcroForm
    from .pd_non_terminal_field import PDNonTerminalField

_FT_KEY: COSName = COSName.get_pdf_name("FT")
_FF: COSName = COSName.get_pdf_name("Ff")


class PDPushButton(PDButton):
    """``/FT /Btn`` with ``FLAG_PUSHBUTTON`` set. Mirrors PDFBox
    ``PDPushButton``.

    Push buttons do not retain a value: ``get_value`` / ``get_default_value`` /
    ``get_value_as_string`` return empty strings, ``get_export_values`` returns
    an empty list, and ``set_export_values`` rejects non-empty arguments per
    upstream.
    """

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
            self.set_field_flags(self.FLAG_PUSHBUTTON)

    # ---------- upstream behavior overrides ----------

    def get_value(self) -> str:
        return ""

    def get_default_value(self) -> str:
        return ""

    def get_value_as_string(self) -> str:
        return ""

    def get_export_values(self) -> list[str]:
        return []

    def set_export_values(self, values: list[str] | None) -> None:
        if values:
            raise ValueError(
                "A PDPushButton shall not use the Opt entry in the field dictionary"
            )
        super().set_export_values(values)

    def get_on_values(self) -> KeysView[str]:
        # Upstream PDPushButton.getOnValues returns Collections.emptySet();
        # an empty dict's keys view is an equivalent empty ordered set.
        return {}.keys()

    # ---------- appearance regeneration ----------

    def regenerate_appearance(self) -> None:
        """Rebuild each widget's ``/AP /N`` from its ``/MK`` caption /
        background / border. Push buttons hold no value, so unlike
        :meth:`PDTextField.set_value` and :meth:`PDCheckBox.set_value`
        there's no value-mutation path that doubles as a regenerate
        trigger — callers who change the widget's ``/MK`` must invoke
        this explicitly."""
        from .pd_appearance_generator import PDAppearanceGenerator

        PDAppearanceGenerator().generate(self)

    def construct_appearances(self) -> None:
        """Rebuild widget appearances for this push button.

        Upstream ``PDPushButton.constructAppearances`` is a no-op (no
        appearance handler is wired in upstream). Wave 1305 routes the
        call through :class:`PDAppearanceGenerator` so
        :meth:`refresh_appearances` produces a usable ``/AP /N`` from
        the widget's ``/MK`` caption / background / border — keeping the
        lite surface consistent with the Tx / Ch paths.
        """
        from .pd_appearance_generator import PDAppearanceGenerator

        PDAppearanceGenerator().generate(self)


__all__ = ["PDPushButton"]
