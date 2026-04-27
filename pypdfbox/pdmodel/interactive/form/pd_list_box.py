from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos import COSDictionary, COSName

from .pd_choice import PDChoice

if TYPE_CHECKING:
    from .pd_acro_form import PDAcroForm
    from .pd_non_terminal_field import PDNonTerminalField

_FT_KEY: COSName = COSName.get_pdf_name("FT")


class PDListBox(PDChoice):
    """``/FT /Ch`` with ``FLAG_COMBO`` cleared. Mirrors PDFBox ``PDListBox``."""

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
            self.set_combo(False)

    # ---------- /V + appearance ----------

    def set_value(
        self,
        value: list[str] | str | None,
        regenerate_appearance: bool = False,
    ) -> None:
        """Set the field's ``/V`` value.

        When ``regenerate_appearance=True``, also rebuilds each widget's
        ``/AP /N`` flat-text appearance via :class:`PDAppearanceGenerator`
        — for list boxes the selected values are rendered one per line.
        The default (``False``) preserves the historical lite-port
        behaviour of writing the value alone.
        """
        super().set_value(value)
        if regenerate_appearance:
            from .pd_appearance_generator import PDAppearanceGenerator

            PDAppearanceGenerator().generate(self)


__all__ = ["PDListBox"]
