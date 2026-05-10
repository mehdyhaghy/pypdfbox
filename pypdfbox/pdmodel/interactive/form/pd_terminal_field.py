from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSDictionary,
    COSInteger,
    COSName,
    COSString,
)
from pypdfbox.pdmodel.interactive.annotation import PDAnnotationWidget

from .pd_field import PDField

if TYPE_CHECKING:
    from pypdfbox.pdmodel.fdf.fdf_field import FDFField
    from pypdfbox.pdmodel.interactive.action import PDFormFieldAdditionalActions

    from .pd_acro_form import PDAcroForm
    from .pd_non_terminal_field import PDNonTerminalField

_logger = logging.getLogger(__name__)

_KIDS: COSName = COSName.get_pdf_name("Kids")
_AA: COSName = COSName.get_pdf_name("AA")
_FT: COSName = COSName.get_pdf_name("FT")
_FF: COSName = COSName.get_pdf_name("Ff")
_V: COSName = COSName.get_pdf_name("V")
_T: COSName = COSName.get_pdf_name("T")
_SET_FF: COSName = COSName.get_pdf_name("SetFf")
_CLR_FF: COSName = COSName.get_pdf_name("ClrFf")
_F: COSName = COSName.get_pdf_name("F")


class PDTerminalField(PDField):
    """Leaf field base. Mirrors PDFBox ``PDTerminalField`` lite surface."""

    def __init__(
        self,
        form: PDAcroForm,
        field: COSDictionary | None = None,
        parent: PDNonTerminalField | None = None,
    ) -> None:
        super().__init__(form, field, parent)

    def is_terminal(self) -> bool:
        return True

    # ---------- /FT, /Ff inheritable walk (self -> parent only) ----------

    def get_field_type(self) -> str | None:
        """Return ``/FT`` walking only self → parent.

        Mirrors upstream ``PDTerminalField.getFieldType`` (lines 88-96): a
        terminal field's type is taken from its own dictionary or from the
        nearest ancestor non-terminal field. Unlike :meth:`PDField.get_field_type`
        the walk stops at the AcroForm — this matches upstream's terminal
        semantics where the form-level ``/FT`` is irrelevant for an already-
        terminal node.
        """
        item = self._field.get_dictionary_object(_FT)
        if isinstance(item, COSName):
            return item.name
        if self._parent is not None:
            return self._parent.get_field_type()
        return None

    def get_field_flags(self) -> int:
        """Return ``/Ff`` walking only self → parent.

        Mirrors upstream ``PDTerminalField.getFieldFlags`` (lines 72-85): own
        flags win; otherwise inherit from the parent non-terminal node.
        Stops at the AcroForm to match upstream.
        """
        item = self._field.get_dictionary_object(_FF)
        if isinstance(item, COSInteger):
            return item.value
        if self._parent is not None:
            return self._parent.get_field_flags()
        return 0

    # ---------- /AA (additional actions) ----------

    def set_actions(
        self, actions: PDFormFieldAdditionalActions | COSDictionary | None
    ) -> None:
        """Set ``/AA`` form-field additional actions.

        Mirrors upstream ``PDTerminalField.setActions(PDFormFieldAdditionalActions)``
        — the narrower typed override over :meth:`PDField.set_actions`.
        """
        if actions is None:
            self._field.remove_item(_AA)
            return
        self._field.set_item(
            _AA,
            actions.get_cos_object() if hasattr(actions, "get_cos_object") else actions,
        )

    # ---------- widgets (/Kids) ----------

    def get_widgets(self) -> list[PDAnnotationWidget]:
        """Returns typed widget annotations.

        When ``/Kids`` is absent the field itself acts as the widget (PDF
        spec — single-widget shortcut where the widget dictionary is merged
        into the field dictionary), so a single :class:`PDAnnotationWidget`
        wrapping ``self._field`` is returned.
        """
        kids = self._field.get_dictionary_object(_KIDS)
        if not isinstance(kids, COSArray):
            return [PDAnnotationWidget(self._field)]
        out: list[PDAnnotationWidget] = []
        for i in range(kids.size()):
            entry = kids.get_object(i)
            if isinstance(entry, COSDictionary):
                out.append(PDAnnotationWidget(entry))
        return out

    def set_widgets(self, widgets: list[PDAnnotationWidget]) -> None:
        """Replace ``/Kids`` with the supplied widget annotations.

        Each widget's ``/Parent`` is wired back at this field. Lite version:
        always writes a ``/Kids`` array even for a single widget. Upstream's
        single-widget merge optimisation (where the lone widget dictionary
        is folded into the field dictionary) is deferred — we keep the
        explicit ``/Kids`` form so the object graph stays predictable.
        """
        kids = COSArray()
        for w in widgets:
            cos = w.get_cos_object()
            w.set_parent(self)
            kids.add(cos)
        self._field.set_item(_KIDS, kids)

    # ---------- FDF import / export ----------

    def import_fdf(self, fdf_field: FDFField) -> None:
        """Import a value and flags from an :class:`FDFField`.

        Mirrors upstream ``PDTerminalField.importFDF(FDFField)`` (lines
        99-139) and the leg of ``PDField.importFDF`` it relies on (lines
        237-306). Sequence:

        1. Apply the FDF ``/V`` to the typed terminal field via the
           subclass-specific ``set_value`` (string / name / array / stream
           values are all handled by :meth:`FDFField.get_cos_value`).
        2. Apply ``/Ff``; otherwise apply the ``/SetFf`` / ``/ClrFf``
           bit-mutation pair. Per upstream: ``SetFf`` and ``ClrFf`` are
           ignored when ``/Ff`` is set.
        3. For each widget annotation, apply ``/F``; otherwise apply
           ``/SetF`` / ``/ClrF`` analogously to flag bit mutation.
        """
        # /V — set via the typed subclass set_value so PDChoice/PDButton/
        # PDTextField each format the value correctly.
        field_value: COSBase | None = fdf_field.get_cos_value()
        if field_value is not None:
            self._apply_fdf_value(field_value)

        # /Ff vs /SetFf/ClrFf — upstream uses Integer null discrimination.
        # We mirror by checking presence of the COS keys directly so absent
        # entries differ from "explicitly set to 0".
        cos = fdf_field.get_cos_object()
        ff_present = isinstance(cos.get_dictionary_object(_FF), COSInteger)
        if ff_present:
            self.set_field_flags(fdf_field.get_field_flags())
        else:
            field_flags = self.get_field_flags()
            if isinstance(cos.get_dictionary_object(_SET_FF), COSInteger):
                field_flags = field_flags | fdf_field.get_set_field_flags()
                self.set_field_flags(field_flags)
            if isinstance(cos.get_dictionary_object(_CLR_FF), COSInteger):
                # Clear the bits that are set in /ClrFf — see upstream
                # PDField.importFDF for the bit-arithmetic comment.
                clr_value = fdf_field.get_clear_field_flags() ^ 0xFFFFFFFF
                field_flags = field_flags & clr_value
                self.set_field_flags(field_flags)

        # Per-widget /F vs /SetF / /ClrF.
        widget_f_present = isinstance(cos.get_dictionary_object(_F), COSInteger)
        widget_f = fdf_field.get_widget_field_flags() if widget_f_present else None
        for widget in self.get_widgets():
            if widget_f is not None:
                widget.set_annotation_flags(widget_f)
                continue
            annot_flags = widget.get_annotation_flags()
            if isinstance(cos.get_dictionary_object(COSName.get_pdf_name("SetF")), COSInteger):
                annot_flags = annot_flags | fdf_field.get_set_widget_field_flags()
                widget.set_annotation_flags(annot_flags)
            if isinstance(cos.get_dictionary_object(COSName.get_pdf_name("ClrF")), COSInteger):
                clr_value = fdf_field.get_clear_widget_field_flags() ^ 0xFFFFFFFF
                annot_flags = annot_flags & clr_value
                widget.set_annotation_flags(annot_flags)

    def _apply_fdf_value(self, value: COSBase) -> None:
        """Dispatch an FDF ``/V`` payload to the typed ``set_value``.

        Mirrors the ``importFDF`` value branch in upstream
        ``PDField.importFDF(FDFField)``. The value-coercion rules are:

        * ``COSName`` → name string passed to :meth:`set_value`
        * ``COSString`` → decoded string
        * ``COSStream`` → decoded text string
        * ``COSArray`` → only meaningful for choice fields; passed through
          as a list of strings (handled by :class:`PDChoice.set_value`).
          For non-choice fields the raw COSBase is written under ``/V``
          to mirror upstream's IOException-equivalent fallback being
          unreachable for well-formed FDFs.
        """
        from pypdfbox.cos import COSStream  # noqa: PLC0415 — avoid I/O cycle

        if isinstance(value, COSName):
            self.set_value(value.name)
            return
        if isinstance(value, COSString):
            self.set_value(value.get_string())
            return
        if isinstance(value, COSStream):
            self.set_value(value.to_text_string())
            return
        if isinstance(value, COSArray):
            from .pd_choice import PDChoice  # noqa: PLC0415 — defer import

            if isinstance(self, PDChoice):
                self.set_value(value.to_cos_string_string_list())
                return
            # Non-choice + COSArray is upstream's IOException branch. For
            # robustness we write the raw entry; tests can guard against
            # malformed inputs.
            self._field.set_item(_V, value)
            return
        # Mirrors upstream's "throw IOException" — narrow it to OSError so
        # callers can catch via the standard I/O hierarchy.
        raise OSError(f"Error: Unknown type for field import: {value!r}")

    def export_fdf(self) -> FDFField:
        """Build an :class:`FDFField` snapshot of this terminal field.

        Mirrors upstream ``PDTerminalField.exportFDF`` (lines 142-152):
        copies the partial-name and the raw ``/V`` entry. The ``/Kids`` walk
        is intentionally absent — upstream's comment notes that kids on a
        terminal field are widget annotations, not nested fields.
        """
        from pypdfbox.pdmodel.fdf.fdf_field import FDFField  # noqa: PLC0415

        fdf_field = FDFField()
        fdf_field.set_partial_field_name(self.get_partial_name())
        v = self._field.get_dictionary_object(_V)
        if v is not None:
            fdf_field.get_cos_object().set_item(_V, v)
        return fdf_field

    # ---------- appearance ----------

    def apply_change(self) -> None:
        """No-op on the lite surface.

        Upstream triggers appearance regeneration (``PDAppearanceGenerator``)
        when the field's value or geometry changes. Appearance regeneration
        is deferred — see ``CHANGES.md``.
        """
        _logger.debug(
            "PDTerminalField.apply_change: appearance regeneration deferred"
        )

    def construct_appearances(self) -> None:
        """No-op on the lite surface.

        Upstream rebuilds the ``/AP`` appearance streams for every widget of
        this field via ``PDAppearanceGenerator``. Deferred — see
        ``CHANGES.md``.
        """
        _logger.debug(
            "PDTerminalField.construct_appearances: appearance regeneration deferred"
        )


class PDFieldStub(PDTerminalField):
    """Generic concrete terminal field used until typed subclasses land."""

    def set_value(self, value: object | None) -> None:
        """Stub set_value — stores the value verbatim under ``/V``."""
        if value is None:
            self._field.remove_item(_V)
            return
        if isinstance(value, COSBase):
            self._field.set_item(_V, value)
            return
        if isinstance(value, str):
            self._field.set_string(_V, value)
            return
        raise TypeError(
            f"PDFieldStub.set_value expected None, str or COSBase; got {type(value).__name__}"
        )


__all__ = ["PDTerminalField", "PDFieldStub"]
