from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos import COSArray, COSBase, COSDictionary, COSName, COSString
from pypdfbox.pdmodel.common.filespecification.pd_file_specification import (
    PDFileSpecification,
)

from .pd_action import PDAction

if TYPE_CHECKING:
    from pypdfbox.pdmodel.interactive.form.pd_field import PDField

_F: COSName = COSName.get_pdf_name("F")
_FIELDS: COSName = COSName.get_pdf_name("Fields")
_FLAGS: COSName = COSName.get_pdf_name("Flags")

# PDF 32000-1 §12.7.5.2 Table 237 — SubmitForm /Flags bit positions.
# Stored as 1 << (bit - 1) so call sites read like the spec.
_FLAG_INCLUDE_EXCLUDE = 1 << 0           # bit 1
_FLAG_INCLUDE_NO_VALUE_FIELDS = 1 << 1   # bit 2
_FLAG_EXPORT_FORMAT = 1 << 2             # bit 3
_FLAG_GET_METHOD = 1 << 3                # bit 4
_FLAG_SUBMIT_COORDINATES = 1 << 4        # bit 5
_FLAG_XFDF = 1 << 5                      # bit 6
_FLAG_INCLUDE_APPEND_SAVES = 1 << 6      # bit 7
_FLAG_INCLUDE_ANNOTATIONS = 1 << 7       # bit 8
_FLAG_SUBMIT_PDF = 1 << 8                # bit 9
_FLAG_CANONICAL_FORMAT = 1 << 9          # bit 10
_FLAG_EXCL_NON_USER_ANNOTS = 1 << 10     # bit 11
_FLAG_EXCL_F_KEY = 1 << 11               # bit 12
# bit 13 is reserved
_FLAG_EMBED_FORM = 1 << 13               # bit 14


class PDActionSubmitForm(PDAction):
    """SubmitForm action. Mirrors PDFBox ``PDActionSubmitForm``.

    PDF 32000-1 §12.7.5.2 Table 236 (SubmitForm action) and Table 237
    (Flags). pypdfbox layers the per-bit predicates from Table 237 on
    top of the upstream ``getFlags``/``setFlags`` surface so callers can
    address the named flags symbolically.
    """

    SUB_TYPE = "SubmitForm"

    def __init__(self, action: COSDictionary | None = None) -> None:
        super().__init__(action, None if action is not None else self.SUB_TYPE)

    # ---------- /F (file specification) ----------

    def get_file(self) -> PDFileSpecification | None:
        """Return ``/F`` typed as a :class:`PDFileSpecification` (simple or
        complex form), or ``None`` when ``/F`` is absent. Mirrors upstream
        ``getFile()``."""
        return PDFileSpecification.create_fs(self._action.get_dictionary_object(_F))

    def set_file(
        self,
        value: PDFileSpecification | COSBase | str | bytes | None,
    ) -> None:
        """Set ``/F``. Accepts a :class:`PDFileSpecification`, a raw
        ``COSBase``, a ``str``/``bytes`` URL (stored as ``COSString``), or
        ``None`` to remove the entry."""
        if value is None:
            self._action.remove_item(_F)
            return
        if isinstance(value, PDFileSpecification):
            self._action.set_item(_F, value.get_cos_object())
            return
        if isinstance(value, (str, bytes)):
            self._action.set_string(_F, value)
            return
        self._action.set_item(_F, value)

    # ---------- URL convenience over /F ----------

    def get_url(self) -> str | None:
        """Return ``/F`` as a URL string when stored in simple (``COSString``)
        form, or by reading ``/F`` from a complex file specification.
        Returns ``None`` when no URL can be derived."""
        raw = self._action.get_dictionary_object(_F)
        if raw is None:
            return None
        if isinstance(raw, COSString):
            return raw.get_string()
        fs = PDFileSpecification.create_fs(raw)
        if fs is None:
            return None
        return fs.get_file()

    def set_url(self, value: str | None) -> None:
        """Store ``/F`` as a simple ``COSString`` URL, or remove ``/F``
        when ``value`` is ``None``."""
        if value is None:
            self._action.remove_item(_F)
            return
        self._action.set_string(_F, value)

    # ---------- /Fields ----------

    def get_fields(self) -> list[PDField] | None:
        """Return ``/Fields`` as a list of typed :class:`PDField`
        subclasses (dispatched through :class:`PDFieldFactory`).

        Returns ``None`` when ``/Fields`` is absent. Entries that are
        plain partial-name strings (PDF allows fully-qualified names in
        the ``/Fields`` array — PDF 32000-1 §12.7.5.2) are resolved
        against the document's AcroForm when one can be located; if no
        matching field is found, the entry is dropped from the result."""
        value = self._action.get_dictionary_object(_FIELDS)
        if not isinstance(value, COSArray):
            return None
        from pypdfbox.pdmodel.interactive.form.pd_acro_form import PDAcroForm
        from pypdfbox.pdmodel.interactive.form.pd_field_factory import (
            PDFieldFactory,
        )

        # We synthesise a throwaway empty AcroForm so PDFieldFactory has a
        # parent to chain inheritable lookups against — we don't have a
        # PDDocument reference at this layer.
        form = PDAcroForm()
        result: list[PDField] = []
        for i in range(value.size()):
            entry = value.get_object(i)
            if isinstance(entry, COSDictionary):
                wrapped = PDFieldFactory.create_field(form, entry, None)
                if wrapped is not None:
                    result.append(wrapped)
            elif isinstance(entry, COSString):
                # Fully-qualified field name — leave to the caller; can't
                # resolve without an AcroForm. Skip to keep the list typed.
                continue
        return result

    def get_cos_fields(self) -> COSArray | None:
        """Raw access to the ``/Fields`` array. Returns ``None`` when
        ``/Fields`` is absent. Mirrors upstream ``getFields()`` (which
        returns the raw ``COSArray``); pypdfbox exposes the typed list
        as :meth:`get_fields` and keeps this for round-tripping."""
        value = self._action.get_dictionary_object(_FIELDS)
        if isinstance(value, COSArray):
            return value
        return None

    def set_fields(
        self,
        values: COSArray | list[PDField] | list[COSBase] | None,
    ) -> None:
        """Set ``/Fields``. Accepts a ``COSArray``, a list of
        :class:`PDField` instances, a list of ``COSBase`` entries, or
        ``None`` to remove."""
        if values is None:
            self._action.remove_item(_FIELDS)
            return
        if isinstance(values, COSArray):
            self._action.set_item(_FIELDS, values)
            return
        from pypdfbox.pdmodel.interactive.form.pd_field import PDField

        array = COSArray()
        for item in values:
            if isinstance(item, PDField):
                array.add(item.get_cos_object())
            elif isinstance(item, COSBase):
                array.add(item)
            else:
                raise TypeError(
                    "set_fields entries must be PDField or COSBase, got "
                    f"{type(item).__name__}"
                )
        self._action.set_item(_FIELDS, array)

    # ---------- /Flags ----------

    def get_flags(self) -> int:
        """Return ``/Flags``, defaulting to ``0`` when absent (Table 236)."""
        return self._action.get_int(_FLAGS, 0)

    def set_flags(self, value: int) -> None:
        """Set ``/Flags`` (Table 237 bit-field)."""
        self._action.set_int(_FLAGS, value)

    # ---------- Table 237 per-bit predicates ----------

    def _get_flag(self, mask: int) -> bool:
        return (self.get_flags() & mask) != 0

    def _set_flag(self, mask: int, value: bool) -> None:
        flags = self.get_flags()
        flags = (flags | mask) if value else (flags & ~mask)
        self.set_flags(flags)

    # bit 1 — Include/Exclude
    def is_include(self, b: bool | None = None) -> bool:
        """When ``b`` is ``None`` (the default), return whether the
        Include/Exclude flag (Table 237 bit 1) is set. When ``b`` is a
        bool, set the flag and return the new value — mirrors upstream
        Java overloads collapsed onto one Pythonic signature."""
        if b is not None:
            self._set_flag(_FLAG_INCLUDE_EXCLUDE, b)
        return self._get_flag(_FLAG_INCLUDE_EXCLUDE)

    def set_include(self, b: bool) -> None:
        self._set_flag(_FLAG_INCLUDE_EXCLUDE, b)

    # bit 2 — IncludeNoValueFields
    def is_include_no_value_fields(self) -> bool:
        """Return whether the IncludeNoValueFields flag (Table 237 bit 2)
        is set. When ``True`` the submission includes successful fields
        that have no value; when ``False`` such fields are excluded."""
        return self._get_flag(_FLAG_INCLUDE_NO_VALUE_FIELDS)

    def set_include_no_value_fields(self, b: bool) -> None:
        self._set_flag(_FLAG_INCLUDE_NO_VALUE_FIELDS, b)

    # bit 3 — ExportFormat
    def is_export_format(self) -> bool:
        return self._get_flag(_FLAG_EXPORT_FORMAT)

    def set_export_format(self, b: bool) -> None:
        self._set_flag(_FLAG_EXPORT_FORMAT, b)

    # bit 4 — GetMethod
    def is_get_method(self) -> bool:
        return self._get_flag(_FLAG_GET_METHOD)

    def set_get_method(self, b: bool) -> None:
        self._set_flag(_FLAG_GET_METHOD, b)

    # bit 5 — SubmitCoordinates
    def is_submit_coordinates(self) -> bool:
        return self._get_flag(_FLAG_SUBMIT_COORDINATES)

    def set_submit_coordinates(self, b: bool) -> None:
        self._set_flag(_FLAG_SUBMIT_COORDINATES, b)

    # bit 6 — XFDF
    def is_xfdf(self) -> bool:
        return self._get_flag(_FLAG_XFDF)

    def set_xfdf(self, b: bool) -> None:
        self._set_flag(_FLAG_XFDF, b)

    # bit 7 — IncludeAppendSaves
    def is_include_append_saves(self) -> bool:
        return self._get_flag(_FLAG_INCLUDE_APPEND_SAVES)

    def set_include_append_saves(self, b: bool) -> None:
        self._set_flag(_FLAG_INCLUDE_APPEND_SAVES, b)

    # bit 8 — IncludeAnnotations
    def is_include_annotations(self) -> bool:
        return self._get_flag(_FLAG_INCLUDE_ANNOTATIONS)

    def set_include_annotations(self, b: bool) -> None:
        self._set_flag(_FLAG_INCLUDE_ANNOTATIONS, b)

    # bit 9 — SubmitPDF
    def is_submit_pdf(self) -> bool:
        return self._get_flag(_FLAG_SUBMIT_PDF)

    def set_submit_pdf(self, b: bool) -> None:
        self._set_flag(_FLAG_SUBMIT_PDF, b)

    # bit 10 — CanonicalFormat
    def is_canonical_format(self) -> bool:
        return self._get_flag(_FLAG_CANONICAL_FORMAT)

    def set_canonical_format(self, b: bool) -> None:
        self._set_flag(_FLAG_CANONICAL_FORMAT, b)

    # bit 11 — ExclNonUserAnnots
    def is_excl_non_user_annots(self) -> bool:
        return self._get_flag(_FLAG_EXCL_NON_USER_ANNOTS)

    def set_excl_non_user_annots(self, b: bool) -> None:
        self._set_flag(_FLAG_EXCL_NON_USER_ANNOTS, b)

    # bit 12 — ExclFKey
    def is_excl_f_key(self) -> bool:
        return self._get_flag(_FLAG_EXCL_F_KEY)

    def set_excl_f_key(self, b: bool) -> None:
        self._set_flag(_FLAG_EXCL_F_KEY, b)

    # bit 14 — EmbedForm
    def is_embed_form(self) -> bool:
        return self._get_flag(_FLAG_EMBED_FORM)

    def set_embed_form(self, b: bool) -> None:
        self._set_flag(_FLAG_EMBED_FORM, b)


__all__ = ["PDActionSubmitForm"]
