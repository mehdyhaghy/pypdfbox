from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos import COSArray, COSBase, COSDictionary, COSName

from .pd_field_factory import PDFieldFactory

if TYPE_CHECKING:
    from .pd_field import PDField

_FIELDS: COSName = COSName.get_pdf_name("Fields")
_SIG_FLAGS: COSName = COSName.get_pdf_name("SigFlags")
_NEED_APPEARANCES: COSName = COSName.get_pdf_name("NeedAppearances")
_XFA: COSName = COSName.get_pdf_name("XFA")

_FLAG_SIGNATURES_EXIST = 1
_FLAG_APPEND_ONLY = 1 << 1


class PDAcroForm:
    """The /AcroForm dictionary. Mirrors PDFBox ``PDAcroForm`` lite surface.

    Deferred: ``flatten``, ``refresh_appearances``, ``import_fdf``/``export_fdf``,
    ``get_default_resources``/``set_default_resources``, ``get_default_appearance``,
    ``get_q``, ``get_calc_order``, signature scripting handler, field caching,
    ``get_field_iterator``/``get_field_tree``. Typed PDXFAResource is also deferred —
    :meth:`xfa` returns the raw COS entry.
    """

    def __init__(
        self,
        document: object | None = None,
        dictionary: COSDictionary | None = None,
    ) -> None:
        self._document = document
        if dictionary is None:
            self._dictionary = COSDictionary()
            self._dictionary.set_item(_FIELDS, COSArray())
        else:
            self._dictionary = dictionary

    # ---------- core ----------

    def get_cos_object(self) -> COSDictionary:
        return self._dictionary

    def get_dictionary(self) -> COSDictionary:
        return self._dictionary

    def get_document(self) -> object | None:
        return self._document

    # ---------- /Fields ----------

    def get_fields(self) -> list[PDField]:
        raw = self._dictionary.get_dictionary_object(_FIELDS)
        if not isinstance(raw, COSArray):
            return []
        out: list[PDField] = []
        for i in range(raw.size()):
            entry = raw.get_object(i)
            if not isinstance(entry, COSDictionary):
                continue
            field = PDFieldFactory.create_field(self, entry, None)
            if field is not None:
                out.append(field)
        return out

    def set_fields(self, fields: list[PDField]) -> None:
        arr = COSArray()
        for f in fields:
            arr.add(f.get_cos_object())
        self._dictionary.set_item(_FIELDS, arr)

    def get_field(self, fully_qualified_name: str) -> PDField | None:
        """Locate a field by its fully-qualified name (".\"-joined)."""
        if fully_qualified_name is None:
            return None
        for top in self.get_fields():
            found = self._find_field(top, fully_qualified_name)
            if found is not None:
                return found
        return None

    def _find_field(self, field: PDField, fqn: str) -> PDField | None:
        if field.get_fully_qualified_name() == fqn:
            return field
        if not field.is_terminal():
            from .pd_non_terminal_field import PDNonTerminalField

            assert isinstance(field, PDNonTerminalField)
            for child in field.get_children():
                found = self._find_field(child, fqn)
                if found is not None:
                    return found
        return None

    # ---------- /SigFlags ----------

    def _get_sig_flags(self) -> int:
        return self._dictionary.get_int(_SIG_FLAGS, 0)

    def _set_sig_flag(self, mask: int, value: bool) -> None:
        flags = self._get_sig_flags()
        if value:
            flags |= mask
        else:
            flags &= ~mask
        self._dictionary.set_int(_SIG_FLAGS, flags)

    def is_signatures_exist(self) -> bool:
        return bool(self._get_sig_flags() & _FLAG_SIGNATURES_EXIST)

    def set_signatures_exist(self, value: bool) -> None:
        self._set_sig_flag(_FLAG_SIGNATURES_EXIST, value)

    def is_appendonly(self) -> bool:
        return bool(self._get_sig_flags() & _FLAG_APPEND_ONLY)

    def set_appendonly(self, value: bool) -> None:
        self._set_sig_flag(_FLAG_APPEND_ONLY, value)

    # ---------- /NeedAppearances ----------

    def is_need_appearances(self) -> bool:
        return self._dictionary.get_boolean(_NEED_APPEARANCES, False)

    def set_need_appearances(self, value: bool) -> None:
        self._dictionary.set_boolean(_NEED_APPEARANCES, value)

    # ---------- /XFA (raw — typed PDXFAResource deferred) ----------

    def xfa(self) -> COSBase | None:
        return self._dictionary.get_dictionary_object(_XFA)


__all__ = ["PDAcroForm"]
