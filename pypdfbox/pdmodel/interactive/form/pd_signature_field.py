from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos import COSBase, COSDictionary, COSName

from .pd_terminal_field import PDTerminalField

if TYPE_CHECKING:
    from .pd_acro_form import PDAcroForm
    from .pd_non_terminal_field import PDNonTerminalField

_FT_KEY: COSName = COSName.get_pdf_name("FT")
_V: COSName = COSName.get_pdf_name("V")
_SV: COSName = COSName.get_pdf_name("SV")
_LOCK: COSName = COSName.get_pdf_name("Lock")


class PDSignatureField(PDTerminalField):
    """``/FT /Sig`` signature field. Mirrors PDFBox ``PDSignatureField`` lite
    surface.

    Deferred upstream behavior: typed ``PDSignature`` / ``PDSeedValue`` /
    ``PDSignatureLock`` wrapping is not implemented — accessors return raw
    ``COSBase`` / ``COSDictionary``. Auto-naming the partial field name on
    fresh construction is also deferred.
    """

    FT = "Sig"

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

    # ---------- /V ----------

    def get_signature(self) -> COSBase | None:
        return self._field.get_dictionary_object(_V)

    def get_value(self) -> COSBase | None:
        return self.get_signature()

    def set_value(self, value: COSBase | None) -> None:
        if value is None:
            self._field.remove_item(_V)
        else:
            self._field.set_item(_V, value)

    # ---------- /SV ----------

    def get_seed_value(self) -> COSDictionary | None:
        item = self._field.get_dictionary_object(_SV)
        if isinstance(item, COSDictionary):
            return item
        return None

    def set_seed_value(self, seed: COSDictionary | None) -> None:
        if seed is None:
            self._field.remove_item(_SV)
        else:
            self._field.set_item(_SV, seed)

    # ---------- /Lock ----------

    def get_lock(self) -> COSDictionary | None:
        item = self._field.get_dictionary_object(_LOCK)
        if isinstance(item, COSDictionary):
            return item
        return None

    def set_lock(self, lock: COSDictionary | None) -> None:
        if lock is None:
            self._field.remove_item(_LOCK)
        else:
            self._field.set_item(_LOCK, lock)


__all__ = ["PDSignatureField"]
