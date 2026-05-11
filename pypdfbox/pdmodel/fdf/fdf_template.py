from __future__ import annotations

from pypdfbox.cos import COSArray, COSBoolean, COSDictionary, COSName

from .fdf_field import FDFField, FDFNamedPageReference

_TREF: COSName = COSName.get_pdf_name("TRef")
_FIELDS: COSName = COSName.get_pdf_name("Fields")
_RENAME: COSName = COSName.get_pdf_name("Rename")


class FDFTemplate:
    """FDF page template — entry of an :class:`FDFPage`'s ``/Templates``
    array.

    Mirrors ``org.apache.pdfbox.pdmodel.fdf.FDFTemplate`` (Java
    lines 33-136).
    """

    def __init__(self, template: COSDictionary | None = None) -> None:
        self._template: COSDictionary = (
            template if template is not None else COSDictionary()
        )

    # ---------- COS surface ----------

    def get_cos_object(self) -> COSDictionary:
        """Return the wrapped ``COSDictionary``. Mirrors upstream
        ``getCOSObject()`` (Java line 61)."""
        return self._template

    # ---------- /TRef ----------

    def get_template_reference(self) -> FDFNamedPageReference | None:
        """Return the template reference (``/TRef``) or ``None``.

        Mirrors upstream ``getTemplateReference()`` (Java line 71).
        """
        dict_ = self._template.get_dictionary_object(_TREF)
        if isinstance(dict_, COSDictionary):
            return FDFNamedPageReference(dict_)
        return None

    def set_template_reference(self, ref: FDFNamedPageReference | None) -> None:
        """Set the template reference (``/TRef``).

        Mirrors upstream ``setTemplateReference(FDFNamedPageReference)``
        (Java line 82).
        """
        if ref is None:
            self._template.remove_item(_TREF)
            return
        self._template.set_item(_TREF, ref.get_cos_object())

    # ---------- /Fields ----------

    def get_fields(self) -> list[FDFField] | None:
        """Return the template's fields (``/Fields``) or ``None``.

        Mirrors upstream ``getFields()`` (Java line 92).
        """
        array = self._template.get_dictionary_object(_FIELDS)
        if not isinstance(array, COSArray):
            return None
        fields: list[FDFField] = []
        for i in range(array.size()):
            entry = array.get_object(i)
            if isinstance(entry, COSDictionary):
                fields.append(FDFField(entry))
        return fields

    def set_fields(self, fields: list[FDFField] | None) -> None:
        """Set the template's fields (``/Fields``).

        Mirrors upstream ``setFields(List<FDFField>)`` (Java line 112).
        """
        if fields is None:
            self._template.remove_item(_FIELDS)
            return
        array = COSArray()
        for field in fields:
            array.add(field.get_cos_object())
        self._template.set_item(_FIELDS, array)

    # ---------- /Rename ----------

    def should_rename(self) -> bool:
        """``True`` when imported fields may be renamed on conflict
        (``/Rename``). Default is ``False``.

        Mirrors upstream ``shouldRename()`` (Java line 122).
        """
        value = self._template.get_dictionary_object(_RENAME)
        if isinstance(value, COSBoolean):
            return value.get_value()
        return False

    def set_rename(self, value: bool) -> None:
        """Set the rename flag (``/Rename``).

        Mirrors upstream ``setRename(boolean)`` (Java line 132).
        """
        self._template.set_boolean(_RENAME, bool(value))


__all__ = ["FDFTemplate"]
