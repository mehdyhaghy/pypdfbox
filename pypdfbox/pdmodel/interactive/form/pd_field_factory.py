from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName

if TYPE_CHECKING:
    from .pd_acro_form import PDAcroForm
    from .pd_field import PDField
    from .pd_non_terminal_field import PDNonTerminalField

_KIDS: COSName = COSName.get_pdf_name("Kids")
_SUBTYPE: COSName = COSName.get_pdf_name("Subtype")
_T: COSName = COSName.get_pdf_name("T")
_FT: COSName = COSName.get_pdf_name("FT")
_FF: COSName = COSName.get_pdf_name("Ff")
_PARENT: COSName = COSName.get_pdf_name("Parent")
_P: COSName = COSName.get_pdf_name("P")


def _find_field_type(
    dic: COSDictionary, seen: set[int] | None = None
) -> str | None:
    """Walk ``/Parent`` (then ``/P``) up the dictionary chain to find ``/FT``.

    Mirrors upstream ``PDFieldFactory.findFieldType``. Cycle-safe per
    PDFBOX-5896 — a dictionary already visited returns ``None``.
    """
    if seen is None:
        seen = set()
    key = id(dic)
    if key in seen:
        return None
    seen.add(key)
    item = dic.get_dictionary_object(_FT)
    if isinstance(item, COSName):
        return item.name
    base = dic.get_dictionary_object(_PARENT)
    if not isinstance(base, COSDictionary):
        base = dic.get_dictionary_object(_P)
    if isinstance(base, COSDictionary):
        return _find_field_type(base, seen)
    return None


def _resolve_field_type(
    field: COSDictionary,
    parent: PDNonTerminalField | None,
    form: PDAcroForm,
) -> str | None:
    item = field.get_dictionary_object(_FT)
    if isinstance(item, COSName):
        return item.name
    if parent is not None:
        return parent.get_field_type()
    item = form.get_cos_object().get_dictionary_object(_FT)
    if isinstance(item, COSName):
        return item.name
    return None


def _resolve_field_flags(
    field: COSDictionary,
    parent: PDNonTerminalField | None,
    form: PDAcroForm,
) -> int:
    item = field.get_dictionary_object(_FF)
    if isinstance(item, COSInteger):
        return item.value
    if parent is not None:
        return parent.get_field_flags()
    item = form.get_cos_object().get_dictionary_object(_FF)
    if isinstance(item, COSInteger):
        return item.value
    return 0


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
    def find_field_type(field: COSDictionary) -> str | None:
        """Resolve ``/FT`` for a field dictionary, walking ``/Parent`` (then
        ``/P``) up the chain with cycle detection.

        Mirrors upstream ``PDFieldFactory.findFieldType``. Lifted to a public
        helper because callers outside the factory benefit from the same walk.
        """
        return _find_field_type(field)

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
        # Terminal: dispatch on /FT (walks parent chain via inherited lookup).
        ft = _resolve_field_type(field, parent, form)
        if ft == "Tx":
            from .pd_text_field import PDTextField
            return PDTextField(form, field, parent)
        if ft == "Btn":
            from .pd_button import PDButton
            ff = _resolve_field_flags(field, parent, form)
            if ff & PDButton.FLAG_PUSHBUTTON:
                from .pd_push_button import PDPushButton
                return PDPushButton(form, field, parent)
            if ff & PDButton.FLAG_RADIO:
                from .pd_radio_button import PDRadioButton
                return PDRadioButton(form, field, parent)
            from .pd_check_box import PDCheckBox
            return PDCheckBox(form, field, parent)
        if ft == "Ch":
            from .pd_choice import PDChoice
            ff = _resolve_field_flags(field, parent, form)
            if ff & PDChoice.FLAG_COMBO:
                from .pd_combo_box import PDComboBox
                return PDComboBox(form, field, parent)
            from .pd_list_box import PDListBox
            return PDListBox(form, field, parent)
        if ft == "Sig":
            from .pd_signature_field import PDSignatureField
            return PDSignatureField(form, field, parent)
        return PDFieldStub(form, field, parent)


__all__ = ["PDFieldFactory"]
