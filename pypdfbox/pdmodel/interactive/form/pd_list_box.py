from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos import COSDictionary, COSName

from .pd_choice import PDChoice

if TYPE_CHECKING:
    from .pd_acro_form import PDAcroForm
    from .pd_non_terminal_field import PDNonTerminalField

_FT_KEY: COSName = COSName.get_pdf_name("FT")
_TI: COSName = COSName.get_pdf_name("TI")


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

    # ---------- /TI ----------

    def get_top_index(self) -> int:
        """Return the ``/TI`` top index value, defaulting to ``0``.

        Mirrors PDFBox ``PDListBox.getTopIndex``. ``PDChoice`` also exposes
        this helper in the current port for backwards compatibility, but the
        upstream public surface belongs to ``PDListBox``.
        """
        return self._field.get_int(_TI, 0)

    def set_top_index(self, top_index: int | None) -> None:
        """Set or remove the ``/TI`` top index value.

        Passing ``None`` removes the entry, matching upstream
        ``PDListBox.setTopIndex(null)``.
        """
        if top_index is None:
            self._field.remove_item(_TI)
        else:
            self._field.set_int(_TI, top_index)

    def has_top_index(self) -> bool:
        """Predicate — return ``True`` when ``/TI`` is set on this field's own
        dictionary.

        Pypdfbox-only convenience: lets callers distinguish "explicit
        ``/TI = 0``" from "no ``/TI`` entry" without rereading the dict
        directly. :meth:`get_top_index` returns ``0`` for both cases.
        """
        return super().has_top_index()

    def clear_top_index(self) -> None:
        """Remove this list box's local ``/TI`` top-index entry."""
        super().clear_top_index()

    # ---------- /V + appearance ----------

    def set_value(
        self,
        value: list[str] | str | None,
        regenerate_appearance: bool | None = None,
    ) -> None:
        """Set the field's ``/V`` value.

        Mirrors upstream ``PDListBox.setValue`` → ``applyChange()``: after
        writing ``/V`` each widget's ``/AP /N`` flat-text appearance (the
        selected values rendered one per line) is rebuilt via
        :class:`PDAppearanceGenerator`, **unless** the AcroForm carries
        ``/NeedAppearances true``. ``regenerate_appearance`` defaults to
        ``None`` = follow that upstream gate; ``True`` / ``False`` force
        regeneration on / off (the latter is the legacy lite-port "write the
        value alone" path).
        """
        super().set_value(value)
        if self._should_regenerate_appearance(regenerate_appearance):
            from .pd_appearance_generator import PDAppearanceGenerator

            PDAppearanceGenerator().generate(self)

    def construct_appearances(self) -> None:
        """Rebuild widget appearances for this list box.

        Mirrors upstream ``PDListBox.constructAppearances`` via the port's
        shared :class:`PDAppearanceGenerator`.
        """
        from .pd_appearance_generator import PDAppearanceGenerator

        PDAppearanceGenerator().generate(self)


__all__ = ["PDListBox"]
