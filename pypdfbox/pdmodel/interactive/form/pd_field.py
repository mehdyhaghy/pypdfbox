from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos import COSArray, COSBase, COSDictionary, COSInteger, COSName

if TYPE_CHECKING:
    from pypdfbox.pdmodel.fdf.fdf_field import FDFField
    from pypdfbox.pdmodel.interactive.action import PDFormFieldAdditionalActions
    from pypdfbox.pdmodel.interactive.annotation import PDAnnotationWidget

    from .pd_acro_form import PDAcroForm
    from .pd_non_terminal_field import PDNonTerminalField

_T: COSName = COSName.get_pdf_name("T")
_TU: COSName = COSName.get_pdf_name("TU")
_TM: COSName = COSName.get_pdf_name("TM")
_FT: COSName = COSName.get_pdf_name("FT")
_FF: COSName = COSName.get_pdf_name("Ff")
_AA: COSName = COSName.get_pdf_name("AA")
_PARENT: COSName = COSName.get_pdf_name("Parent")


class PDField:
    """Abstract base for AcroForm fields. Mirrors PDFBox ``PDField`` lite surface."""

    FLAG_READ_ONLY = 1
    FLAG_REQUIRED = 1 << 1
    FLAG_NO_EXPORT = 1 << 2

    def __init__(
        self,
        form: PDAcroForm,
        field: COSDictionary | None = None,
        parent: PDNonTerminalField | None = None,
    ) -> None:
        self._acro_form = form
        self._field = field if field is not None else COSDictionary()
        self._parent = parent

    # ---------- core ----------

    @staticmethod
    def from_dictionary(
        form: PDAcroForm,
        field: COSDictionary,
        parent: PDNonTerminalField | None = None,
    ) -> PDField | None:
        """Reading-side factory — wrap ``field`` into the right ``PDField``.

        Mirrors upstream's package-private ``PDField.fromDictionary`` which
        forwards to :meth:`PDFieldFactory.create_field`. Exposed publicly
        here because pypdfbox does not have Java's package-private
        visibility — callers outside the form package occasionally need
        the same dispatch (e.g. when re-wrapping a kid dictionary that
        was reached via raw COS traversal).
        """
        from .pd_field_factory import PDFieldFactory

        return PDFieldFactory.create_field(form, field, parent)

    def get_cos_object(self) -> COSDictionary:
        return self._field

    def get_acro_form(self) -> PDAcroForm:
        return self._acro_form

    def get_parent(self) -> PDNonTerminalField | None:
        return self._parent

    def set_parent(self, parent: PDNonTerminalField | None) -> None:
        self._parent = parent
        if parent is None:
            self._field.remove_item(_PARENT)
        else:
            self._field.set_item(_PARENT, parent.get_cos_object())

    # ---------- /T, /TU, /TM ----------

    def get_partial_name(self) -> str | None:
        return self._field.get_string(_T)

    def set_partial_name(self, name: str | None) -> None:
        # Mirrors upstream PDField.setPartialName: a partial name shall not
        # contain a period. Upstream raises IllegalArgumentException; we use
        # the closest Python analogue, ValueError.
        if name is not None and "." in name:
            raise ValueError(
                f"A field partial name shall not contain a period character: {name}"
            )
        self._field.set_string(_T, name)

    def has_partial_name(self) -> bool:
        """Return ``True`` when this field has a local string-like ``/T``."""
        return self._field.has_string(_T)

    def clear_partial_name(self) -> None:
        """Remove this field's local ``/T`` partial-name entry."""
        self._field.remove_item(_T)

    def get_alternate_field_name(self) -> str | None:
        return self._field.get_string(_TU)

    def set_alternate_field_name(self, name: str | None) -> None:
        self._field.set_string(_TU, name)

    def has_alternate_field_name(self) -> bool:
        """Return ``True`` when this field has a local string-like ``/TU``."""
        return self._field.has_string(_TU)

    def clear_alternate_field_name(self) -> None:
        """Remove this field's local ``/TU`` alternate-name entry."""
        self._field.remove_item(_TU)

    def get_mapping_name(self) -> str | None:
        return self._field.get_string(_TM)

    def set_mapping_name(self, name: str | None) -> None:
        self._field.set_string(_TM, name)

    def has_mapping_name(self) -> bool:
        """Return ``True`` when this field has a local string-like ``/TM``."""
        return self._field.has_string(_TM)

    def clear_mapping_name(self) -> None:
        """Remove this field's local ``/TM`` mapping-name entry."""
        self._field.remove_item(_TM)

    # ---------- inheritable attribute walk ----------

    def get_inheritable_attribute(self, key: COSName) -> COSBase | None:
        """Walks self -> parent chain -> acroForm dictionary.

        Mirrors upstream ``PDField.getInheritableAttribute`` exactly: the
        decision to stop walking is keyed on ``containsKey`` (presence),
        **not** on the resolved value being non-null. A field that carries
        ``key`` explicitly — even when it resolves to ``COSNull`` — shadows
        any ancestor value and stops the walk, returning the locally
        resolved object (``None`` for an explicit null). Pypdfbox previously
        gated on ``get_dictionary_object(key) is not None``, which let a
        present-but-null entry fall through to the parent and inherit a
        value upstream would have suppressed.
        """
        if self._field.contains_key(key):
            return self._field.get_dictionary_object(key)
        if self._parent is not None:
            return self._parent.get_inheritable_attribute(key)
        return self._acro_form.get_cos_object().get_dictionary_object(key)

    def get_field_type(self) -> str | None:
        item = self.get_inheritable_attribute(_FT)
        if isinstance(item, COSName):
            return item.name
        return None

    def get_field_flags(self) -> int:
        item = self.get_inheritable_attribute(_FF)
        from pypdfbox.cos import COSInteger

        if isinstance(item, COSInteger):
            return item.value
        return 0

    def set_field_flags(self, flags: int) -> None:
        self._field.set_int(_FF, flags)

    def has_field_flags(self) -> bool:
        """Return ``True`` when this field has a local integer ``/Ff`` entry."""
        return isinstance(self._field.get_dictionary_object(_FF), COSInteger)

    def clear_field_flags(self) -> None:
        """Remove this field's local ``/Ff`` flag entry."""
        self._field.remove_item(_FF)

    # ---------- fully qualified name ----------

    def get_fully_qualified_name(self) -> str | None:
        """Return the dotted fully-qualified name, or ``None`` when no ``/T``
        partial name exists anywhere in the self -> parent chain.

        Mirrors upstream ``PDField.getFullyQualifiedName`` exactly: the result
        is built from the parent's fully-qualified name and this field's partial
        name (``get_partial_name`` — ``None`` when ``/T`` is absent). When both
        are ``None`` the result is ``None``; when only the parent name exists it
        is returned alone; when only the partial exists it is returned alone;
        when both exist they join with a ``.``. A *present-but-empty* ``/T``
        (``/T ()``) yields ``""`` (not ``None``), matching upstream's
        ``getPartialName() != null`` distinction. Pypdfbox previously coerced a
        missing ``/T`` to ``""`` here, diverging from upstream's ``null`` — fixed
        in wave 1542 and pinned by the live oracle.
        """
        parent_fqn = (
            None if self._parent is None else self._parent.get_fully_qualified_name()
        )
        final_name = self.get_partial_name()
        if final_name is not None and parent_fqn is not None:
            return f"{parent_fqn}.{final_name}"
        if parent_fqn is not None:
            return parent_fqn
        return final_name

    # ---------- flag bit accessors ----------

    def _set_flag(self, mask: int, value: bool) -> None:
        flags = self.get_field_flags()
        if value:
            flags |= mask
        else:
            flags &= ~mask
        self.set_field_flags(flags)

    def is_read_only(self) -> bool:
        return bool(self.get_field_flags() & self.FLAG_READ_ONLY)

    def set_read_only(self, value: bool) -> None:
        self._set_flag(self.FLAG_READ_ONLY, value)

    def is_required(self) -> bool:
        return bool(self.get_field_flags() & self.FLAG_REQUIRED)

    def set_required(self, value: bool) -> None:
        self._set_flag(self.FLAG_REQUIRED, value)

    def is_no_export(self) -> bool:
        return bool(self.get_field_flags() & self.FLAG_NO_EXPORT)

    def set_no_export(self, value: bool) -> None:
        self._set_flag(self.FLAG_NO_EXPORT, value)

    # ---------- /AA (additional actions) ----------

    def get_actions(self) -> PDFormFieldAdditionalActions | None:
        from pypdfbox.pdmodel.interactive.action import PDFormFieldAdditionalActions

        value = self._field.get_dictionary_object(_AA)
        if isinstance(value, COSDictionary):
            return PDFormFieldAdditionalActions(value)
        return None

    def set_actions(
        self, aa: PDFormFieldAdditionalActions | COSDictionary | None
    ) -> None:
        if aa is None:
            self._field.remove_item(_AA)
            return
        self._field.set_item(
            _AA,
            aa.get_cos_object() if hasattr(aa, "get_cos_object") else aa,
        )

    def has_actions(self) -> bool:
        """Return ``True`` when this field has a local ``/AA`` dictionary."""
        return isinstance(self._field.get_dictionary_object(_AA), COSDictionary)

    def clear_actions(self) -> None:
        """Remove this field's local ``/AA`` additional-actions dictionary."""
        self._field.remove_item(_AA)

    # ---------- abstract ----------

    def is_terminal(self) -> bool:
        raise NotImplementedError

    def get_value_as_string(self) -> str:
        """Return a string representation of ``/V`` (or empty string).

        Mirrors upstream ``PDField.getValueAsString`` (line 119) — abstract
        in Java; concrete subclasses (text / button / choice / signature /
        non-terminal) override.
        """
        raise NotImplementedError

    def set_value(self, value: object | None) -> None:
        """Set the field value.

        Mirrors upstream ``PDField.setValue(String)`` (line 128) — abstract
        in Java. Subclasses accept their own typed value (string for text,
        list[str] for choice, etc.). Upstream throws ``IOException`` when
        the value cannot be set; pypdfbox subclasses raise ``OSError`` /
        ``ValueError`` to match.
        """
        raise NotImplementedError

    def get_widgets(self) -> list[PDAnnotationWidget]:
        """Return widget annotations associated with this field.

        Mirrors upstream ``PDField.getWidgets`` (line 142) — abstract in
        Java. :class:`PDNonTerminalField` returns an empty list (no visual
        representation); :class:`PDTerminalField` returns one widget per
        ``/Kids`` entry, falling back to a single widget wrapping the field
        dictionary itself when ``/Kids`` is absent (single-widget shortcut).
        """
        raise NotImplementedError

    def export_fdf(self) -> FDFField:
        """Export this field (and its children) as an :class:`FDFField`.

        Mirrors upstream ``PDField.exportFDF`` (line 311) — abstract /
        package-private in Java. Concrete subclasses
        (:class:`PDTerminalField`, :class:`PDNonTerminalField`) override.
        """
        raise NotImplementedError

    # ---------- FDF import (delegates to typed subclass) ----------

    def import_fdf(self, fdf_field: FDFField) -> None:
        """Import a value and flags from an :class:`FDFField`.

        Mirrors upstream ``PDField.importFDF(FDFField)`` (lines 237-306) —
        package-private in Java. The base implementation handles the
        non-terminal-field branch (raw COS write under ``/V``) plus the
        ``/Ff`` / ``/SetFf`` / ``/ClrFf`` bit-mutation pair. Terminal
        subclasses override to apply typed value coercion via ``set_value``;
        see :meth:`PDTerminalField.import_fdf`.
        """
        from pypdfbox.cos import COSInteger as _COSInt

        field_value = fdf_field.get_cos_value()
        if field_value is not None:
            # Non-terminal branch: write the raw COS entry under /V. Terminal
            # subclasses override import_fdf and never reach this leg.
            self._field.set_item(COSName.get_pdf_name("V"), field_value)

        cos = fdf_field.get_cos_object()
        ff_key = COSName.get_pdf_name("Ff")
        if isinstance(cos.get_dictionary_object(ff_key), _COSInt):
            self.set_field_flags(fdf_field.get_field_flags())
            return

        field_flags = self.get_field_flags()
        set_ff_key = COSName.get_pdf_name("SetFf")
        clr_ff_key = COSName.get_pdf_name("ClrFf")
        if isinstance(cos.get_dictionary_object(set_ff_key), _COSInt):
            field_flags = field_flags | fdf_field.get_set_field_flags()
            self.set_field_flags(field_flags)
        if isinstance(cos.get_dictionary_object(clr_ff_key), _COSInt):
            # See upstream PDField.importFDF (lines 295-303): clear the bits
            # that are set in /ClrFf using a 32-bit complement-and-AND.
            clr_value = fdf_field.get_clear_field_flags() ^ 0xFFFFFFFF
            field_flags = field_flags & clr_value
            self.set_field_flags(field_flags)

    # ---------- /Kids descent ----------

    def find_kid(self, name: list[str], name_index: int) -> PDField | None:
        """Walk ``/Kids`` looking for a field whose ``/T`` matches ``name[name_index]``.

        Mirrors upstream package-private ``PDField.findKid``. Recurses until
        the path is consumed. Returns ``None`` if no kid matches.
        """
        from .pd_field_factory import PDFieldFactory
        from .pd_non_terminal_field import PDNonTerminalField

        kids = self._field.get_dictionary_object(COSName.get_pdf_name("Kids"))
        if not isinstance(kids, COSArray):
            return None
        result: PDField | None = None
        for i in range(kids.size()):
            if result is not None:
                break
            kid_dict = kids.get_object(i)
            if not isinstance(kid_dict, COSDictionary):
                continue
            kid_name = kid_dict.get_string(_T)
            if kid_name == name[name_index]:
                parent = self if isinstance(self, PDNonTerminalField) else None
                result = PDFieldFactory.create_field(
                    self._acro_form, kid_dict, parent
                )
                if result is not None and len(name) > name_index + 1:
                    result = result.find_kid(name, name_index + 1)
        return result

    # ---------- equality / repr ----------

    def __eq__(self, other: object) -> bool:
        # Mirrors upstream PDField.equals: two fields are equal iff their
        # backing COSDictionary objects compare equal. COSDictionary uses
        # identity equality in pypdfbox, so this collapses to "same dict".
        if self is other:
            return True
        if not isinstance(other, PDField):
            return False
        return self._field == other.get_cos_object()

    def equals(self, other: object) -> bool:
        """Mirror upstream ``PDField.equals(Object)`` (lines 484-498).

        Java-named delegate to :meth:`__eq__` for callers porting code
        verbatim from PDFBox. Two fields are equal iff their backing
        ``COSDictionary`` objects compare equal — identity-via-dict.
        """
        return self.__eq__(other)

    def __hash__(self) -> int:
        # Hash on the dictionary identity so equal fields hash equal.
        return hash(id(self._field))

    def hash_code(self) -> int:
        """Mirror upstream ``PDField.hashCode()`` (lines 503-507).

        Java-named delegate to :meth:`__hash__`. Returns ``Objects.hash``
        of the backing dictionary; in pypdfbox this is the dictionary's
        Python-side identity hash so equal fields hash equal.
        """
        return self.__hash__()

    def __str__(self) -> str:
        # Mirrors upstream PDField.toString: "<fqn>{type: <Class> value: <V>}".
        fqn = self.get_fully_qualified_name() or ""
        value = self.get_inheritable_attribute(COSName.get_pdf_name("V"))
        return f"{fqn}{{type: {type(self).__name__} value: {value}}}"

    def to_string(self) -> str:
        """Mirror upstream ``PDField.toString()`` (lines 473-478).

        Java-named delegate to :meth:`__str__` returning
        ``"<fqn>{type: <Class> value: <V>}"``.
        """
        return self.__str__()

    def __repr__(self) -> str:
        return self.__str__()


__all__ = ["PDField"]
