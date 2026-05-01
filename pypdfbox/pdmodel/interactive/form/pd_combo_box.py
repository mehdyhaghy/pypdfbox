from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos import COSDictionary, COSName

from .pd_choice import PDChoice

if TYPE_CHECKING:
    from .pd_acro_form import PDAcroForm
    from .pd_non_terminal_field import PDNonTerminalField

_FT_KEY: COSName = COSName.get_pdf_name("FT")


class PDComboBox(PDChoice):
    """``/FT /Ch`` with ``FLAG_COMBO`` set. Mirrors PDFBox ``PDComboBox``."""

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
            self.set_combo(True)

    def is_edit(self) -> bool:
        return bool(self.get_field_flags() & self.FLAG_EDIT)

    def set_edit(self, value: bool) -> None:
        self._set_flag(self.FLAG_EDIT, value)

    # ---------- /V + appearance ----------

    def set_value(
        self,
        value: list[str] | str | None,
        regenerate_appearance: bool = False,
    ) -> None:
        """Set the field's ``/V`` value.

        When ``regenerate_appearance=True``, also rebuilds each widget's
        ``/AP /N`` flat-text appearance via :class:`PDAppearanceGenerator`
        — for combo boxes this is the selected option string. The default
        (``False``) preserves the historical lite-port behaviour of
        writing the value alone.
        """
        super().set_value(value)
        if regenerate_appearance:
            from .pd_appearance_generator import PDAppearanceGenerator

            PDAppearanceGenerator().generate(self)

    def construct_appearances(self) -> None:
        """Rebuild widget appearances for this combo box.

        Mirrors upstream ``PDComboBox.constructAppearances`` via the port's
        shared :class:`PDAppearanceGenerator`.
        """
        from .pd_appearance_generator import PDAppearanceGenerator

        PDAppearanceGenerator().generate(self)


__all__ = ["PDComboBox"]
