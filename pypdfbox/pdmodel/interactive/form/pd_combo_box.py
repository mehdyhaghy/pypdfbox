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

    # Upstream PDComboBox.java declares ``FLAG_EDIT`` as a private constant
    # on this class. PDChoice carries the same value in the lite port for
    # subclass dispatch convenience, but expose it here too for parity with
    # upstream callers that reference ``PDComboBox.FLAG_EDIT``.
    FLAG_EDIT = PDChoice.FLAG_EDIT

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
        regenerate_appearance: bool | None = None,
    ) -> None:
        """Set the field's ``/V`` value.

        Mirrors upstream ``PDComboBox.setValue`` → ``applyChange()``: after
        writing ``/V`` each widget's ``/AP /N`` flat-text appearance (the
        selected option string) is rebuilt via :class:`PDAppearanceGenerator`,
        **unless** the AcroForm carries ``/NeedAppearances true``.
        ``regenerate_appearance`` defaults to ``None`` = follow that upstream
        gate; ``True`` / ``False`` force regeneration on / off (the latter is
        the legacy lite-port "write the value alone" path).
        """
        super().set_value(value)
        if self._should_regenerate_appearance(regenerate_appearance):
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
