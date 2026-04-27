from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName

from .pd_action import PDAction

_FIELDS: COSName = COSName.get_pdf_name("Fields")
_FLAGS: COSName = COSName.get_pdf_name("Flags")

# Bit 1 of /Flags (PDF 32000-1 §12.7.5.3 Table 239): when clear (default),
# the /Fields entry is the include set — only those fields are reset. When
# set, /Fields is the exclude set — every field is reset *except* those
# listed.
_FLAG_INCLUDE_EXCLUDE = 1


class PDActionResetForm(PDAction):
    """ResetForm action. Mirrors PDFBox ``PDActionResetForm`` lite surface.

    Adds an ``is_include`` / ``set_include`` pair for the include/exclude
    flag in ``/Flags`` bit 1 (PDF 32000-1 §12.7.5.3 Table 239) that
    upstream does not expose as a typed accessor.
    """

    SUB_TYPE = "ResetForm"

    def __init__(self, action: COSDictionary | None = None) -> None:
        super().__init__(action, None if action is not None else self.SUB_TYPE)

    # ---------- /Fields ----------

    def get_fields(self) -> COSArray | None:
        """Returns the raw ``/Fields`` ``COSArray`` (or ``None`` when
        absent / wrong type) — upstream parity with
        ``PDActionResetForm.getFields()`` which returns ``COSArray``.

        Each entry identifies a field via partial-name string, fully
        qualified name, or an indirect reference to the field dictionary
        (PDF 32000-1 §12.7.5.3). Callers that want typed
        :class:`PDField` wrappers should resolve entries against the
        document's :class:`PDAcroForm`.
        """
        value = self._action.get_dictionary_object(_FIELDS)
        if isinstance(value, COSArray):
            return value
        return None

    def set_fields(self, values: COSArray | None) -> None:
        """Sets the raw ``/Fields`` ``COSArray``. ``None`` removes the
        entry."""
        if values is None:
            self._action.remove_item(_FIELDS)
            return
        self._action.set_item(_FIELDS, values)

    # ---------- /Flags ----------

    def get_flags(self) -> int:
        return self._action.get_int(_FLAGS, 0)

    def set_flags(self, value: int) -> None:
        self._action.set_int(_FLAGS, value)

    # ---------- /Flags bit 1: Include/Exclude ----------

    def is_include(self) -> bool:
        """Returns the include/exclude semantic of ``/Flags`` bit 1.

        ``False`` (default — bit clear): ``/Fields`` is the include set;
        only the listed fields are reset.

        ``True`` (bit set): ``/Fields`` is the exclude set; every field is
        reset *except* those listed.
        """
        return (self.get_flags() & _FLAG_INCLUDE_EXCLUDE) != 0

    def set_include(self, b: bool) -> None:
        flags = self.get_flags()
        if b:
            flags |= _FLAG_INCLUDE_EXCLUDE
        else:
            flags &= ~_FLAG_INCLUDE_EXCLUDE
        self.set_flags(flags)


__all__ = ["PDActionResetForm"]
