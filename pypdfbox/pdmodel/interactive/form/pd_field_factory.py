from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos import COSArray, COSDictionary, COSName

if TYPE_CHECKING:
    from .pd_acro_form import PDAcroForm
    from .pd_field import PDField
    from .pd_non_terminal_field import PDNonTerminalField

_KIDS: COSName = COSName.get_pdf_name("Kids")
_SUBTYPE: COSName = COSName.get_pdf_name("Subtype")
_T: COSName = COSName.get_pdf_name("T")


class PDFieldFactory:
    """Factory dispatching ``COSDictionary`` -> ``PDField`` subclass.

    Mirrors PDFBox ``PDFieldFactory``. Type-specific dispatch on ``/FT``
    (``Btn``/``Tx``/``Ch``/``Sig``) is deferred until typed subclasses are
    ported; for now, terminal fields are returned as the generic
    :class:`PDFieldStub`.
    """

    FIELD_TYPE_TEXT = "Tx"
    FIELD_TYPE_BUTTON = "Btn"
    FIELD_TYPE_CHOICE = "Ch"
    FIELD_TYPE_SIGNATURE = "Sig"

    @staticmethod
    def create_field(
        form: PDAcroForm,
        field: COSDictionary,
        parent: PDNonTerminalField | None = None,
    ) -> PDField | None:
        from .pd_non_terminal_field import PDNonTerminalField as NTField
        from .pd_terminal_field import PDFieldStub

        if field is None:
            return None
        # Non-terminal detection: /Kids exists with at least one child that
        # is a field (no /Subtype — Subtype indicates a widget annotation).
        kids = field.get_dictionary_object(_KIDS)
        if isinstance(kids, COSArray) and kids.size() > 0:
            for i in range(kids.size()):
                entry = kids.get_object(i)
                if (
                    isinstance(entry, COSDictionary)
                    and entry.get_dictionary_object(_SUBTYPE) is None
                ):
                    return NTField(form, field, parent)
        # Terminal: typed-subtype dispatch deferred — return generic stub.
        return PDFieldStub(form, field, parent)


__all__ = ["PDFieldFactory"]
