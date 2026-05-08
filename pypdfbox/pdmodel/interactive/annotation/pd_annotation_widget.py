from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos import COSDictionary, COSName

from .pd_annotation import PDAnnotation

if TYPE_CHECKING:
    from pypdfbox.pdmodel.interactive.action import (
        PDAction,
        PDAnnotationAdditionalActions,
    )
    from pypdfbox.pdmodel.interactive.form.pd_terminal_field import PDTerminalField

    from .pd_appearance_characteristics_dictionary import (
        PDAppearanceCharacteristicsDictionary,
    )
    from .pd_border_style_dictionary import PDBorderStyleDictionary


_H: COSName = COSName.get_pdf_name("H")
_A: COSName = COSName.get_pdf_name("A")
_AA: COSName = COSName.get_pdf_name("AA")
_BS: COSName = COSName.get_pdf_name("BS")
_MK: COSName = COSName.get_pdf_name("MK")
_PARENT: COSName = COSName.get_pdf_name("Parent")


class PDAnnotationWidget(PDAnnotation):
    """
    Widget annotation — ``/Subtype /Widget``. Mirrors
    ``org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationWidget``.

    Widget annotations represent the visual appearance of interactive form
    fields (PDF 32000-1:2008 §12.5.6.19). When a field has a single
    associated widget, the widget dictionary is typically merged with the
    field dictionary; when there are multiple widgets per field, each is a
    separate annotation pointing back at the field via ``/Parent``.
    """

    SUB_TYPE: str = "Widget"

    # ---------- /H (highlighting mode) constants ----------
    #
    # PDF 32000-1:2008 Table 188: highlighting mode values.

    HIGHLIGHT_MODE_NONE: str = "N"
    HIGHLIGHT_MODE_INVERT: str = "I"
    HIGHLIGHT_MODE_OUTLINE: str = "O"
    HIGHLIGHT_MODE_PUSH: str = "P"
    HIGHLIGHT_MODE_TOGGLE: str = "T"

    def __init__(self, annot: COSDictionary | None = None) -> None:
        super().__init__(annot)
        # The base annotation constructor supplies a missing /Type /Annot but
        # preserves any existing /Type value, matching upstream's tolerant
        # COSDictionary-taking constructor. The widget constructor only stamps
        # the widget subtype.
        self._set_subtype(self.SUB_TYPE)

    # ---------- /H (highlighting mode) ----------

    def get_highlighting_mode(self) -> str:
        """Default per spec is INVERT (``I``)."""
        value = self._dict.get_name(_H)
        return value if value is not None else "I"

    def set_highlighting_mode(self, mode: str | None) -> None:
        if mode is None:
            self._dict.remove_item(_H)
            return
        if mode not in (
            self.HIGHLIGHT_MODE_NONE,
            self.HIGHLIGHT_MODE_INVERT,
            self.HIGHLIGHT_MODE_OUTLINE,
            self.HIGHLIGHT_MODE_PUSH,
            self.HIGHLIGHT_MODE_TOGGLE,
        ):
            raise ValueError(
                f"Invalid highlighting mode {mode!r}; expected one of N, I, O, P, T"
            )
        self._dict.set_name(_H, mode)

    # ---------- /A (action) ----------

    def get_action(self) -> PDAction | None:
        from pypdfbox.pdmodel.interactive.action import PDAction

        value = self._dict.get_dictionary_object(_A)
        if isinstance(value, COSDictionary):
            return PDAction.create(value)
        return None

    def set_action(self, action: PDAction | COSDictionary | None) -> None:
        if action is None:
            self._dict.remove_item(_A)
            return
        self._dict.set_item(
            _A,
            action.get_cos_object() if hasattr(action, "get_cos_object") else action,
        )

    def has_action(self) -> bool:
        """Predicate: is a parsable ``/A`` action dictionary present?

        No upstream equivalent — saves the ``getAction() != null`` round
        trip when callers only need to know whether an activation action
        exists.
        """
        value = self._dict.get_dictionary_object(_A)
        return isinstance(value, COSDictionary)

    def clear_action(self) -> None:
        """Remove the ``/A`` activation action, if present.

        No upstream equivalent — semantic alias for
        ``set_action(None)`` to make intent explicit at the call site.
        """
        self._dict.remove_item(_A)

    # ---------- /AA (additional actions) ----------

    def get_actions(self) -> PDAnnotationAdditionalActions | None:
        """Widget ``/AA`` holds annotation additional actions."""
        from pypdfbox.pdmodel.interactive.action import PDAnnotationAdditionalActions

        value = self._dict.get_dictionary_object(_AA)
        if isinstance(value, COSDictionary):
            return PDAnnotationAdditionalActions(value)
        return None

    def set_actions(
        self, actions: PDAnnotationAdditionalActions | COSDictionary | None
    ) -> None:
        if actions is None:
            self._dict.remove_item(_AA)
            return
        self._dict.set_item(
            _AA,
            actions.get_cos_object() if hasattr(actions, "get_cos_object") else actions,
        )

    def has_actions(self) -> bool:
        """Predicate: is a parsable ``/AA`` additional-actions dictionary
        present?

        No upstream equivalent.
        """
        value = self._dict.get_dictionary_object(_AA)
        return isinstance(value, COSDictionary)

    def clear_actions(self) -> None:
        """Remove the ``/AA`` additional-actions dictionary, if present."""
        self._dict.remove_item(_AA)

    # ---------- /BS (border style) ----------

    def get_border_style(self) -> PDBorderStyleDictionary | None:
        from .pd_border_style_dictionary import PDBorderStyleDictionary

        value = self._dict.get_dictionary_object(_BS)
        if isinstance(value, COSDictionary):
            return PDBorderStyleDictionary(value)
        return None

    def set_border_style(
        self, bs: PDBorderStyleDictionary | COSDictionary | None
    ) -> None:
        if bs is None:
            self._dict.remove_item(_BS)
            return
        self._dict.set_item(
            _BS,
            bs.get_cos_object() if hasattr(bs, "get_cos_object") else bs,
        )

    def has_border_style(self) -> bool:
        """Predicate: is a parsable ``/BS`` border-style dictionary present?

        No upstream equivalent.
        """
        value = self._dict.get_dictionary_object(_BS)
        return isinstance(value, COSDictionary)

    def clear_border_style(self) -> None:
        """Remove the ``/BS`` border-style dictionary, if present."""
        self._dict.remove_item(_BS)

    # ---------- /MK (appearance characteristics) ----------

    def get_appearance_characteristics(
        self,
    ) -> PDAppearanceCharacteristicsDictionary | None:
        from .pd_appearance_characteristics_dictionary import (
            PDAppearanceCharacteristicsDictionary,
        )

        value = self._dict.get_dictionary_object(_MK)
        if isinstance(value, COSDictionary):
            return PDAppearanceCharacteristicsDictionary(value)
        return None

    def set_appearance_characteristics(
        self, ac: PDAppearanceCharacteristicsDictionary | COSDictionary | None
    ) -> None:
        if ac is None:
            self._dict.remove_item(_MK)
            return
        self._dict.set_item(
            _MK,
            ac.get_cos_object() if hasattr(ac, "get_cos_object") else ac,
        )

    def has_appearance_characteristics(self) -> bool:
        """Predicate: is a parsable ``/MK`` appearance-characteristics
        dictionary present?

        No upstream equivalent.
        """
        value = self._dict.get_dictionary_object(_MK)
        return isinstance(value, COSDictionary)

    def clear_appearance_characteristics(self) -> None:
        """Remove the ``/MK`` appearance-characteristics dictionary, if
        present."""
        self._dict.remove_item(_MK)

    # ---------- /Parent (field) ----------

    def get_parent(self) -> COSDictionary | None:
        """Cluster lite stub — returns the raw parent field dict. Typed
        ``PDField`` wrapper would create a circular import between the
        annotation and form packages, so ``/Parent`` stays raw COS for now.
        """
        value = self._dict.get_dictionary_object(_PARENT)
        if isinstance(value, COSDictionary):
            return value
        return None

    def set_parent(self, field: PDTerminalField | COSDictionary | None) -> None:
        """Set the parent field of a widget annotation.

        Mirrors upstream ``setParent(PDTerminalField)`` for multi-widget
        fields, while retaining raw ``COSDictionary`` support for callers
        that already operate at the COS layer.
        """
        if field is None:
            self._dict.remove_item(_PARENT)
            return
        from pypdfbox.pdmodel.interactive.form.pd_terminal_field import (
            PDTerminalField,
        )

        if isinstance(field, PDTerminalField):
            field_dict = field.get_cos_object()
            if field_dict is self._dict:
                raise ValueError(
                    "set_parent() is not to be called for a field that shares "
                    "a dictionary with its only widget"
                )
            self._dict.set_item(_PARENT, field_dict)
            return
        self._dict.set_item(
            _PARENT,
            field.get_cos_object() if hasattr(field, "get_cos_object") else field,
        )

    def has_parent(self) -> bool:
        """Predicate: is a parsable ``/Parent`` field reference present?

        No upstream equivalent — multi-widget fields point widgets at the
        owning field via ``/Parent``; single-widget fields share the
        dictionary and never set this entry.
        """
        value = self._dict.get_dictionary_object(_PARENT)
        return isinstance(value, COSDictionary)

    def clear_parent(self) -> None:
        """Remove the ``/Parent`` field reference, if present.

        No upstream equivalent — semantic alias for ``set_parent(None)``.
        """
        self._dict.remove_item(_PARENT)


__all__ = ["PDAnnotationWidget"]
