from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSDictionary,
    COSInteger,
    COSName,
)

from .pd_field import PDField

if TYPE_CHECKING:
    from pypdfbox.pdmodel.fdf.fdf_field import FDFField
    from pypdfbox.pdmodel.interactive.annotation import PDAnnotationWidget

    from .pd_acro_form import PDAcroForm

_KIDS: COSName = COSName.get_pdf_name("Kids")
_V: COSName = COSName.get_pdf_name("V")
_DV: COSName = COSName.get_pdf_name("DV")
_FT: COSName = COSName.get_pdf_name("FT")
_FF: COSName = COSName.get_pdf_name("Ff")


class PDNonTerminalField(PDField):
    """Non-terminal field — a node whose descendants are fields.

    Mirrors PDFBox ``PDNonTerminalField``.
    """

    def __init__(
        self,
        form: PDAcroForm,
        field: COSDictionary | None = None,
        parent: PDNonTerminalField | None = None,
    ) -> None:
        super().__init__(form, field, parent)

    def is_terminal(self) -> bool:
        return False

    def get_children(self) -> list[PDField]:
        from .pd_field_factory import PDFieldFactory

        kids = self._field.get_dictionary_object(_KIDS)
        if not isinstance(kids, COSArray):
            return []
        out: list[PDField] = []
        parent_dict = self._field
        for i in range(kids.size()):
            entry = kids.get_object(i)
            if not isinstance(entry, COSDictionary):
                continue
            if entry is parent_dict:
                # self-reference guard, mirrors upstream
                continue
            child = PDFieldFactory.create_field(self._acro_form, entry, self)
            if child is not None:
                out.append(child)
        return out

    def set_children(self, children: list[PDField]) -> None:
        kids = COSArray()
        for child in children:
            child.set_parent(self)
            kids.add(child.get_cos_object())
        self._field.set_item(_KIDS, kids)

    # ---------- /V (raw COSBase per upstream) ----------

    def get_value(self) -> COSBase | None:
        """Returns the raw ``/V`` entry on this node. Mirrors upstream
        ``PDNonTerminalField.getValue`` which returns ``COSBase``.

        Per PDF 32000-1 §12.7.4 children inherit ``/V`` from their parent when
        their own ``/V`` is absent — that walk is performed lazily on each
        child via :meth:`PDField.get_inheritable_attribute`. This method does
        not eagerly resolve children's effective values.
        """
        return self._field.get_dictionary_object(_V)

    def set_value(self, value: COSBase | str | None) -> None:
        """Set the value of this non-terminal node.

        Mirrors upstream's two ``setValue`` overloads: ``setValue(COSBase)``
        and ``setValue(String)``. A ``str`` argument is stored as a
        ``COSString`` under ``/V`` (matching upstream's
        ``getCOSObject().setString(COSName.V, value)``). A ``COSBase`` is
        stored as-is. ``None`` removes ``/V``.
        """
        if value is None:
            self._field.remove_item(_V)
        elif isinstance(value, str):
            self._field.set_string(_V, value)
        else:
            self._field.set_item(_V, value)

    def get_value_as_string(self) -> str:
        """String view of own ``/V``; ``""`` when ``/V`` is absent.

        Mirrors upstream ``PDNonTerminalField.getValueAsString`` exactly::

            COSBase fieldValue = getValue();
            return fieldValue != null ? fieldValue.toString() : "";

        i.e. it returns the COS value's ``toString()`` — *not* its decoded
        payload. Each pypdfbox COS type's :meth:`to_string` mirrors the Java
        ``toString()`` form (``COSString{...}``, ``COSName{...}``,
        ``COSInt{...}``, ``COSArray{...}``, ``true``/``false``), so deferring
        to it keeps the rendered value byte-for-byte identical to PDFBox.
        Confirmed against the live oracle (wave 1469): the earlier
        decoded-payload dispatch (``COSString`` -> ``get_string()`` etc.)
        diverged — PDFBox emits ``COSString{shared-value}``, not the bare
        decoded text.
        """
        item = self.get_value()
        if item is None:
            return ""
        return item.to_string()

    # ---------- /DV (raw COSBase per upstream) ----------

    def get_default_value(self) -> COSBase | None:
        """Returns the raw ``/DV`` entry on this node. Mirrors upstream
        ``PDNonTerminalField.getDefaultValue`` which returns ``COSBase``.

        Like :meth:`get_value`, this returns the local value without walking
        the inheritance chain. Per PDF 32000-1 §12.7.4 children inherit
        ``/DV`` lazily via :meth:`PDField.get_inheritable_attribute`.
        """
        return self._field.get_dictionary_object(_DV)

    def set_default_value(self, value: COSBase | None) -> None:
        if value is None:
            self._field.remove_item(_DV)
        else:
            self._field.set_item(_DV, value)

    # ---------- non-inherited /FT, /Ff overrides ----------

    def get_field_type(self) -> str | None:
        """Returns the local ``/FT`` entry without walking the parent chain.

        Mirrors upstream ``PDNonTerminalField.getFieldType`` — non-terminal
        fields carry ``/FT`` as an inheritable attribute for their descendants
        but the type does not logically belong to the non-terminal node itself.
        """
        item = self._field.get_dictionary_object(_FT)
        if isinstance(item, COSName):
            return item.name
        return None

    def get_field_flags(self) -> int:
        """Returns the local ``/Ff`` entry without walking the parent chain.

        Mirrors upstream ``PDNonTerminalField.getFieldFlags`` — there is no
        need to walk up since ``/Ff`` is inherited by descendants, not by this
        node itself.
        """
        item = self._field.get_dictionary_object(_FF)
        if isinstance(item, COSInteger):
            return item.value
        return 0

    # ---------- widgets ----------

    def get_widgets(self) -> list[PDAnnotationWidget]:
        """Non-terminal fields have no widgets — always returns an empty list.

        Mirrors upstream ``PDNonTerminalField.getWidgets`` which returns
        ``Collections.emptyList()``.
        """
        return []

    # ---------- FDF import / export ----------

    def import_fdf(self, fdf_field: FDFField) -> None:
        """Import an :class:`FDFField` subtree into this non-terminal node.

        Mirrors upstream ``PDNonTerminalField.importFDF`` (lines 76-96):
        delegate the local ``/V`` / ``/Ff`` mutation to the base class, then
        walk the FDF ``/Kids`` and recurse into matching pypdfbox children
        (matched by partial-field-name).
        """
        super().import_fdf(fdf_field)

        fdf_kids = fdf_field.get_kids()
        if fdf_kids is None:
            return
        children = self.get_children()
        # Upstream uses an O(n*m) double loop and we mirror it exactly so the
        # match semantics (first-name-wins, repeated FDF kids re-applied)
        # stay identical.
        for fdf_child in fdf_kids:
            for pd_child in children:
                fdf_name = fdf_child.get_partial_field_name()
                if fdf_name is not None and fdf_name == pd_child.get_partial_name():
                    pd_child.import_fdf(fdf_child)

    def export_fdf(self) -> FDFField:
        """Export this non-terminal subtree as an :class:`FDFField`.

        Mirrors upstream ``PDNonTerminalField.exportFDF`` (lines 99-114):
        copy the partial-name and the local ``/V``, then recursively export
        each child as the FDF ``/Kids`` array.
        """
        from pypdfbox.pdmodel.fdf.fdf_field import FDFField  # noqa: PLC0415

        fdf_field = FDFField()
        fdf_field.set_partial_field_name(self.get_partial_name())
        v = self.get_value()
        if v is not None:
            # Upstream calls FDFField.setValue(Object); the COSBase overload
            # writes the raw entry under /V. We mirror that with a direct
            # COS-level write to avoid the type-coercion overload.
            fdf_field.get_cos_object().set_item(_V, v)

        children = self.get_children()
        fdf_children: list[FDFField] = [child.export_fdf() for child in children]
        fdf_field.set_kids(fdf_children)
        return fdf_field


__all__ = ["PDNonTerminalField"]
