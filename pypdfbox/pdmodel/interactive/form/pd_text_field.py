from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos import COSDictionary, COSName, COSNumber, COSStream, COSString

from .pd_variable_text import PDVariableText

if TYPE_CHECKING:
    from .pd_acro_form import PDAcroForm
    from .pd_non_terminal_field import PDNonTerminalField

_FT_KEY: COSName = COSName.get_pdf_name("FT")
_MAX_LEN: COSName = COSName.get_pdf_name("MaxLen")
_V: COSName = COSName.get_pdf_name("V")
_DV: COSName = COSName.get_pdf_name("DV")


class PDTextField(PDVariableText):
    """``/FT /Tx`` text field. Mirrors PDFBox ``PDTextField`` lite surface.

    Deferred upstream behavior: rich-text DOM serialization to ``/RV``.
    """

    FT = "Tx"

    FLAG_MULTILINE = 1 << 12
    FLAG_PASSWORD = 1 << 13
    FLAG_FILE_SELECT = 1 << 20
    FLAG_DO_NOT_SPELL_CHECK = 1 << 22
    FLAG_DO_NOT_SCROLL = 1 << 23
    FLAG_COMB = 1 << 24
    FLAG_RICH_TEXT = 1 << 25

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

    # ---------- flag accessors ----------

    def is_multiline(self) -> bool:
        return bool(self.get_field_flags() & self.FLAG_MULTILINE)

    def set_multiline(self, value: bool) -> None:
        self._set_flag(self.FLAG_MULTILINE, value)

    def is_password(self) -> bool:
        return bool(self.get_field_flags() & self.FLAG_PASSWORD)

    def set_password(self, value: bool) -> None:
        self._set_flag(self.FLAG_PASSWORD, value)

    def is_file_select(self) -> bool:
        return bool(self.get_field_flags() & self.FLAG_FILE_SELECT)

    def set_file_select(self, value: bool) -> None:
        self._set_flag(self.FLAG_FILE_SELECT, value)

    def is_do_not_spell_check(self) -> bool:
        return bool(self.get_field_flags() & self.FLAG_DO_NOT_SPELL_CHECK)

    def do_not_spell_check(self) -> bool:
        """Upstream PDFBox name (``doNotSpellCheck``). Alias for
        :meth:`is_do_not_spell_check`."""
        return self.is_do_not_spell_check()

    def set_do_not_spell_check(self, value: bool) -> None:
        self._set_flag(self.FLAG_DO_NOT_SPELL_CHECK, value)

    def is_do_not_scroll(self) -> bool:
        return bool(self.get_field_flags() & self.FLAG_DO_NOT_SCROLL)

    def do_not_scroll(self) -> bool:
        """Upstream PDFBox name (``doNotScroll``). Alias for
        :meth:`is_do_not_scroll`."""
        return self.is_do_not_scroll()

    def set_do_not_scroll(self, value: bool) -> None:
        self._set_flag(self.FLAG_DO_NOT_SCROLL, value)

    def is_comb(self) -> bool:
        return bool(self.get_field_flags() & self.FLAG_COMB)

    def set_comb(self, value: bool) -> None:
        self._set_flag(self.FLAG_COMB, value)

    def is_rich_text(self) -> bool:
        return bool(self.get_field_flags() & self.FLAG_RICH_TEXT)

    def set_rich_text(self, value: bool) -> None:
        self._set_flag(self.FLAG_RICH_TEXT, value)

    # ---------- /MaxLen ----------

    def get_max_len(self) -> int:
        item = self.get_inheritable_attribute(_MAX_LEN)
        if isinstance(item, COSNumber):
            return item.int_value()
        return -1

    def set_max_len(self, max_len: int) -> None:
        self._field.set_int(_MAX_LEN, max_len)

    def has_max_len(self) -> bool:
        """Predicate — return ``True`` when ``/MaxLen`` is set on this field.

        Pypdfbox-only convenience: distinguishes "no ``/MaxLen`` entry" from
        "``/MaxLen`` explicitly set to ``-1``", which :meth:`get_max_len` cannot
        on its own. Useful for callers serializing only populated keys.
        """
        return self._field.contains_key(_MAX_LEN)

    def remove_max_len(self) -> None:
        """Remove ``/MaxLen`` from this field's own dictionary.

        Pypdfbox-only convenience: complement of :meth:`set_max_len` for
        callers who want to clear the constraint without writing a sentinel
        ``-1``. After this call :meth:`has_max_len` is ``False`` and
        :meth:`get_max_len` returns ``-1``. No-op when ``/MaxLen`` is absent.
        """
        self._field.remove_item(_MAX_LEN)

    def clear_max_len(self) -> None:
        """Alias for :meth:`remove_max_len`, matching local ``clear_*`` style."""
        self.remove_max_len()

    # ---------- /V, /DV ----------

    def get_value(self) -> str:
        """Return the field value as text.

        Mirrors upstream ``PDTextField.getValue`` — walks the inheritable
        ``/V`` chain (self → parent → AcroForm) and decodes via
        ``getStringOrStream``: ``COSString`` returns its decoded text and
        ``COSStream`` returns ``toTextString()``. Returns ``""`` (never
        ``None``) when ``/V`` is missing or any other COS type, matching
        upstream's non-null contract.
        """
        return (
            self._get_string_or_stream(self.get_inheritable_attribute(_V)) or ""
        )

    def set_value(
        self, value: str | None, regenerate_appearance: bool = False
    ) -> None:
        """Set the field's ``/V`` value.

        When ``regenerate_appearance=True``, also rebuilds each widget's
        ``/AP /N`` normal appearance via :class:`PDAppearanceGenerator`.
        The default (``False``) preserves the historical lite-port behaviour
        of writing the value alone — the existing object graph is untouched
        for callers that flatten or re-render externally.
        """
        if value is None:
            self._field.remove_item(_V)
        else:
            self._field.set_string(_V, value)
        if regenerate_appearance:
            from .pd_appearance_generator import PDAppearanceGenerator

            PDAppearanceGenerator().generate(self)

    def get_default_value(self) -> str:
        """Return the default value as text.

        Mirrors upstream ``PDTextField.getDefaultValue`` — walks the
        inheritable ``/DV`` chain and decodes via ``getStringOrStream``,
        accepting either ``COSString`` or ``COSStream`` payloads. Returns
        ``""`` when ``/DV`` is missing.
        """
        return (
            self._get_string_or_stream(self.get_inheritable_attribute(_DV)) or ""
        )

    def set_default_value(self, value: str | None) -> None:
        if value is None:
            self._field.remove_item(_DV)
        else:
            self._field.set_string(_DV, value)

    def has_value(self) -> bool:
        """Predicate — return ``True`` when ``/V`` is set on this field's own
        dictionary.

        Pypdfbox-only convenience: does **not** walk the inheritable chain.
        Use :meth:`get_value` (which falls back to parent + AcroForm) to read
        the effective value. This predicate is useful for callers that need
        to distinguish "field has its own /V" from "field inherits /V".
        """
        return isinstance(self._field.get_dictionary_object(_V), (COSString, COSStream))

    def has_default_value(self) -> bool:
        """Predicate — return ``True`` when ``/DV`` is set on this field's own
        dictionary.

        Pypdfbox-only convenience: like :meth:`has_value`, this checks the
        local dictionary only and does not walk the inheritable chain.
        """
        return isinstance(self._field.get_dictionary_object(_DV), (COSString, COSStream))

    def clear_value(self) -> None:
        """Remove this field's local ``/V`` entry."""
        self._field.remove_item(_V)

    def clear_default_value(self) -> None:
        """Remove this field's local ``/DV`` entry."""
        self._field.remove_item(_DV)

    def get_value_as_string(self) -> str:
        return self.get_value()

    def construct_appearances(self) -> None:
        """Rebuild widget appearances for this text field.

        Mirrors upstream ``PDTextField.constructAppearances`` via the port's
        shared :class:`PDAppearanceGenerator`.
        """
        from .pd_appearance_generator import PDAppearanceGenerator

        PDAppearanceGenerator().generate(self)


__all__ = ["PDTextField"]
