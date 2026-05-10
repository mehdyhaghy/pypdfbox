from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName

if TYPE_CHECKING:
    from .pd_acro_form import PDAcroForm
    from .pd_field import PDField
    from .pd_non_terminal_field import PDNonTerminalField

_KIDS: COSName = COSName.get_pdf_name("Kids")
_T: COSName = COSName.get_pdf_name("T")
_FT: COSName = COSName.get_pdf_name("FT")
_FF: COSName = COSName.get_pdf_name("Ff")
_PARENT: COSName = COSName.get_pdf_name("Parent")
_P: COSName = COSName.get_pdf_name("P")

_KNOWN_FIELD_TYPES: frozenset[str] = frozenset({"Tx", "Btn", "Ch", "Sig"})


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
        item = parent.get_inheritable_attribute(_FT)
        if isinstance(item, COSName):
            return item.name
        return None
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
        item = parent.get_inheritable_attribute(_FF)
        if isinstance(item, COSInteger):
            return item.value
        return 0
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
    def is_known_field_type(field_type: str | None) -> bool:
        """Return ``True`` when ``field_type`` is one of the four PDF
        field-type names (``Btn``/``Tx``/``Ch``/``Sig``).

        Pypdfbox-only convenience built on the constants exposed by upstream
        ``PDFieldFactory``. Useful for callers that have already resolved a
        field's type via :meth:`find_field_type` and want to validate it
        without listing the constants themselves.
        """
        return field_type in _KNOWN_FIELD_TYPES

    @staticmethod
    def create_field(
        form: PDAcroForm,
        field: COSDictionary | None,
        parent: PDNonTerminalField | None = None,
    ) -> PDField | None:
        from .pd_non_terminal_field import PDNonTerminalField as NTField
        from .pd_terminal_field import PDFieldStub

        if field is None:
            return None
        # Non-terminal detection: /Kids exists with at least one child that
        # carries its own /T partial-name. Mirrors upstream — a kid with /T
        # is a field (whereas a kid without /T is a widget annotation only).
        kids = field.get_dictionary_object(_KIDS)
        if isinstance(kids, COSArray) and kids.size() > 0:
            for i in range(kids.size()):
                entry = kids.get_object(i)
                if (
                    isinstance(entry, COSDictionary)
                    and entry.get_string(_T) is not None
                ):
                    return NTField(form, field, parent)
        # Terminal: dispatch on /FT (walks parent chain via inherited lookup).
        ft = _resolve_field_type(field, parent, form)
        if ft == PDFieldFactory.FIELD_TYPE_TEXT:
            from .pd_text_field import PDTextField
            return PDTextField(form, field, parent)
        if ft == PDFieldFactory.FIELD_TYPE_BUTTON:
            return PDFieldFactory.create_button_sub_type(form, field, parent)
        if ft == PDFieldFactory.FIELD_TYPE_CHOICE:
            return PDFieldFactory.create_choice_sub_type(form, field, parent)
        if ft == PDFieldFactory.FIELD_TYPE_SIGNATURE:
            from .pd_signature_field import PDSignatureField
            return PDSignatureField(form, field, parent)
        if ft is not None or field.get_string(_T) is None:
            # PDFBOX-2885: erroneous non-field objects in /Fields are ignored
            # by upstream instead of being wrapped as generic fields.
            return None
        return PDFieldStub(form, field, parent)

    @staticmethod
    def create_choice_sub_type(
        form: PDAcroForm,
        field: COSDictionary,
        parent: PDNonTerminalField | None = None,
    ) -> PDField:
        """Dispatch a ``/FT /Ch`` field to the right choice subclass.

        Mirrors upstream ``PDFieldFactory.createChoiceSubType``. Honours the
        ``Combo`` (bit 18) flag — set → :class:`PDComboBox`, otherwise
        :class:`PDListBox`. ``/Ff`` is resolved through the inheritable
        chain (parent → AcroForm) for parity with terminal-field dispatch.
        """
        from .pd_choice import PDChoice
        flags = _resolve_field_flags(field, parent, form)
        if flags & PDChoice.FLAG_COMBO:
            from .pd_combo_box import PDComboBox
            return PDComboBox(form, field, parent)
        from .pd_list_box import PDListBox
        return PDListBox(form, field, parent)

    @staticmethod
    def create_button_sub_type(
        form: PDAcroForm,
        field: COSDictionary,
        parent: PDNonTerminalField | None = None,
    ) -> PDField:
        """Dispatch a ``/FT /Btn`` field to the right button subclass.

        Mirrors upstream ``PDFieldFactory.createButtonSubType``. Honours
        ``Radio`` (bit 16) → :class:`PDRadioButton`, ``Pushbutton``
        (bit 17) → :class:`PDPushButton`, otherwise :class:`PDCheckBox`.
        ``/Ff`` is resolved through the inheritable chain (parent →
        AcroForm) for parity with terminal-field dispatch.
        """
        from .pd_button import PDButton
        flags = _resolve_field_flags(field, parent, form)
        if flags & PDButton.FLAG_RADIO:
            from .pd_radio_button import PDRadioButton
            return PDRadioButton(form, field, parent)
        if flags & PDButton.FLAG_PUSHBUTTON:
            from .pd_push_button import PDPushButton
            return PDPushButton(form, field, parent)
        from .pd_check_box import PDCheckBox
        return PDCheckBox(form, field, parent)


__all__ = ["PDFieldFactory"]
