from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos import COSDictionary, COSName, COSStream, COSString

from .pd_terminal_field import PDTerminalField

if TYPE_CHECKING:
    from .pd_acro_form import PDAcroForm
    from .pd_non_terminal_field import PDNonTerminalField

_DA: COSName = COSName.get_pdf_name("DA")
_DS: COSName = COSName.get_pdf_name("DS")
_Q: COSName = COSName.get_pdf_name("Q")
_RV: COSName = COSName.get_pdf_name("RV")


class PDVariableText(PDTerminalField):
    """Abstract intermediate for fields with variable text. Mirrors PDFBox
    ``PDVariableText`` lite surface (``/DA``, ``/Q``, ``/DS``, ``/RV``).

    Deferred upstream surface: appearance regeneration on /DA change, the
    Sejda-compat /DA propagation into kid widgets, ``getStringOrStream`` for
    rich-text /RV stream values.
    """

    QUADDING_LEFT = 0
    QUADDING_CENTERED = 1
    QUADDING_RIGHT = 2

    def __init__(
        self,
        form: PDAcroForm,
        field: COSDictionary | None = None,
        parent: PDNonTerminalField | None = None,
    ) -> None:
        super().__init__(form, field, parent)

    # ---------- /DA ----------

    def get_default_appearance(self) -> str | None:
        item = self.get_inheritable_attribute(_DA)
        if isinstance(item, COSString):
            return item.get_string()
        return None

    def set_default_appearance(self, da_value: str | None) -> None:
        self._field.set_string(_DA, da_value)

    # ---------- /DS ----------

    def get_default_style_string(self) -> str | None:
        return self._field.get_string(_DS)

    def set_default_style_string(self, value: str | None) -> None:
        self._field.set_string(_DS, value)

    # ---------- /Q ----------

    def get_q(self) -> int:
        return self._field.get_int(_Q, 0)

    def set_q(self, q: int) -> None:
        self._field.set_int(_Q, q)

    # ---------- /RV ----------

    def get_rich_text_value(self) -> str | None:
        item = self.get_inheritable_attribute(_RV)
        if isinstance(item, COSString):
            return item.get_string()
        if isinstance(item, COSStream):
            try:
                return item.create_input_stream().read().decode("utf-8")
            except Exception:
                return None
        return None

    def set_rich_text_value(self, value: str | None) -> None:
        self._field.set_string(_RV, value)


__all__ = ["PDVariableText"]
