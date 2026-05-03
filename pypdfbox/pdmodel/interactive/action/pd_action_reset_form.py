from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos import COSArray, COSBase, COSDictionary, COSName, COSString

from .pd_action import PDAction

if TYPE_CHECKING:
    from pypdfbox.pdmodel.interactive.form.pd_field import PDField

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

    #: Bit 1 of ``/Flags`` (PDF 32000-1 §12.7.5.3 Table 239) — when set,
    #: ``/Fields`` is interpreted as the exclude set rather than the
    #: include set. Exposed as a public constant so callers can address
    #: the flag symbolically when working with raw flag integers.
    FLAG_INCLUDE_EXCLUDE: int = _FLAG_INCLUDE_EXCLUDE

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

    def set_fields(
        self,
        values: COSArray | list[PDField] | list[COSBase] | None,
    ) -> None:
        """Sets ``/Fields``. Accepts a ``COSArray`` (mirrors upstream
        ``setFields(COSArray)``), a list of :class:`PDField` instances, a
        list of ``COSBase`` entries (each stored as-is — PDF 32000-1
        §12.7.5.3 allows partial names, fully qualified names, or
        indirect field references), or ``None`` to remove the entry.
        """
        if values is None:
            self._action.remove_item(_FIELDS)
            return
        if isinstance(values, COSArray):
            self._action.set_item(_FIELDS, values)
            return
        # Late-import to avoid a hard dependency cycle through pd_action.
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

    def get_field_names(self) -> list[str]:
        """Return the string-form names listed in ``/Fields``.

        PDF 32000-1 §12.7.5.3 lets ``/Fields`` entries be partial names,
        fully qualified names (``COSString``), or indirect references to
        a field dictionary. This helper extracts the string entries —
        dictionary/reference entries are skipped — preserving array
        order. Returns an empty list when ``/Fields`` is absent or
        contains no string entries.
        """
        value = self._action.get_dictionary_object(_FIELDS)
        if not isinstance(value, COSArray):
            return []
        names: list[str] = []
        for i in range(value.size()):
            entry = value.get_object(i)
            if isinstance(entry, COSString):
                names.append(entry.get_string())
        return names

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

    def is_exclude(self) -> bool:
        """Return ``True`` when ``/Fields`` is interpreted as the *exclude*
        set — i.e. every field is reset *except* those listed.

        Counterpart predicate to :meth:`is_include`. Per PDF 32000-1
        §12.7.5.3 Table 239 the include/exclude semantic is encoded by
        bit 1 of ``/Flags``: bit set means exclude. ``is_exclude`` is
        always the logical inverse of :meth:`is_include`; both are
        provided so call-sites can read either polarity naturally."""
        return (self.get_flags() & _FLAG_INCLUDE_EXCLUDE) != 0

    def set_exclude(self, b: bool) -> None:
        """Set ``/Flags`` bit 1 to the exclude polarity. ``True`` flips
        the bit on (``/Fields`` is the exclude set); ``False`` clears it
        (``/Fields`` is the include set — the spec default).

        Counterpart of :meth:`set_include`. ``set_exclude(True)`` and
        ``set_include(False)`` write the same flag state — exposing both
        polarities lets callers read either direction at the call site."""
        self.set_include(b)

    # ---------- predicates ----------

    def has_fields(self) -> bool:
        """``True`` when ``/Fields`` is present on the underlying dictionary
        and is a ``COSArray``. Lets callers branch on field-list presence
        without re-reading the entry. When ``/Fields`` is absent every
        field in the form is reset (PDF 32000-1 §12.7.5.3 Table 239 —
        the spec semantic of an absent ``/Fields`` entry)."""
        return self.get_fields() is not None

    def has_flags(self) -> bool:
        """``True`` when ``/Flags`` is explicitly present on the underlying
        dictionary. Returns ``False`` when ``/Flags`` is absent (which
        defaults to ``0`` per PDF 32000-1 §12.7.5.3 Table 239, i.e. the
        include semantic with no extra flags set)."""
        return self._action.get_dictionary_object(_FLAGS) is not None

    def is_valid(self) -> bool:
        """``True`` when this action's ``/S`` entry equals
        :attr:`SUB_TYPE` (``"ResetForm"``). Useful as a sanity check
        after round-tripping through :meth:`PDAction.create` or when
        constructing the wrapper around a hand-built
        :class:`COSDictionary`."""
        return self.get_sub_type() == self.SUB_TYPE

    def is_empty(self) -> bool:
        """``True`` when the action carries no targeted fields — either
        ``/Fields`` is absent, or it is present but empty. Combined with
        the include/exclude semantic this corresponds to: include + empty
        → "reset nothing"; exclude + empty → "reset everything" (the
        spec default when ``/Fields`` is absent)."""
        fields = self.get_fields()
        return fields is None or fields.size() == 0

    def clear_fields(self) -> None:
        """Remove ``/Fields`` from the underlying dictionary. After this
        call :meth:`get_fields` returns ``None`` and :meth:`has_fields`
        returns ``False``. Per PDF 32000-1 §12.7.5.3 Table 239 an absent
        ``/Fields`` entry combined with the default include semantic
        causes every field in the form to be reset."""
        self._action.remove_item(_FIELDS)

    def clear_flags(self) -> None:
        """Remove ``/Flags`` from the underlying dictionary. After this
        call :meth:`get_flags` returns ``0`` (the spec default) and
        :meth:`has_flags` returns ``False``."""
        self._action.remove_item(_FLAGS)

__all__ = ["PDActionResetForm"]
