from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos import COSDictionary, COSName

from .pd_annotation import PDAnnotation

if TYPE_CHECKING:
    from pypdfbox.pdmodel.interactive.action.pd_action import PDAction
    from pypdfbox.pdmodel.interactive.action.pd_annotation_additional_actions import (
        PDAnnotationAdditionalActions,
    )

    from .pd_appearance_characteristics_dictionary import (
        PDAppearanceCharacteristicsDictionary,
    )

_T: COSName = COSName.get_pdf_name("T")
_MK: COSName = COSName.get_pdf_name("MK")
_A: COSName = COSName.get_pdf_name("A")
_AA: COSName = COSName.get_pdf_name("AA")


def _as_cos_dictionary(value: object, setter_name: str) -> COSDictionary:
    if isinstance(value, COSDictionary):
        return value
    if hasattr(value, "get_cos_object"):
        cos = value.get_cos_object()
        if isinstance(cos, COSDictionary):
            return cos
        raise TypeError(f"{setter_name} expects a COSDictionary-backed wrapper")
    raise TypeError(
        f"{setter_name} expects None, COSDictionary, or wrapper exposing "
        f"get_cos_object(); got {type(value).__name__}"
    )


class PDAnnotationScreen(PDAnnotation):
    """
    Screen annotation — ``/Subtype /Screen``. Mirrors
    ``org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationScreen``.

    A screen annotation specifies a region of a page upon which media
    clips may be played; it also serves as an object from which actions
    can be triggered (PDF 32000-1:2008 §12.5.6.18, Table 187). Not a
    markup annotation — extends :class:`PDAnnotation` directly.
    """

    SUB_TYPE: str = "Screen"

    def __init__(self, annotation_dict: COSDictionary | None = None) -> None:
        super().__init__(annotation_dict)
        if annotation_dict is None:
            self._set_subtype(self.SUB_TYPE)

    # ---------- /T (annotation title) ----------

    def get_title(self) -> str | None:
        return self._dict.get_string(_T)

    def set_title(self, value: str | None) -> None:
        self._dict.set_string(_T, value)

    def has_title(self) -> bool:
        """Predicate: is a non-empty ``/T`` title string present?

        No upstream equivalent — saves callers an extra null/empty check.
        """
        title = self.get_title()
        return title is not None and title != ""

    def clear_title(self) -> None:
        """Remove the ``/T`` title entry, if present."""
        self._dict.remove_item(_T)

    # ---------- /MK (appearance characteristics dictionary) ----------

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
        self,
        mk: PDAppearanceCharacteristicsDictionary | COSDictionary | None,
    ) -> None:
        if mk is None:
            self._dict.remove_item(_MK)
            return
        self._dict.set_item(
            _MK, _as_cos_dictionary(mk, "set_appearance_characteristics")
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

    # ---------- /A (action) ----------

    def get_action(self) -> PDAction | None:
        from pypdfbox.pdmodel.interactive.action.pd_action import PDAction

        value = self._dict.get_dictionary_object(_A)
        if isinstance(value, COSDictionary):
            return PDAction.create(value)
        return None

    def set_action(self, action: PDAction | COSDictionary | None) -> None:
        if action is None:
            self._dict.remove_item(_A)
            return
        self._dict.set_item(_A, _as_cos_dictionary(action, "set_action"))

    def has_action(self) -> bool:
        """Predicate: is a parsable ``/A`` action dictionary present?

        No upstream equivalent.
        """
        value = self._dict.get_dictionary_object(_A)
        return isinstance(value, COSDictionary)

    def clear_action(self) -> None:
        """Remove the ``/A`` action dictionary, if present."""
        self._dict.remove_item(_A)

    # ---------- /AA (additional actions) ----------

    def get_additional_actions(self) -> PDAnnotationAdditionalActions | None:
        from pypdfbox.pdmodel.interactive.action.pd_annotation_additional_actions import (
            PDAnnotationAdditionalActions,
        )

        value = self._dict.get_dictionary_object(_AA)
        if isinstance(value, COSDictionary):
            return PDAnnotationAdditionalActions(value)
        return None

    def set_additional_actions(
        self, aa: PDAnnotationAdditionalActions | COSDictionary | None
    ) -> None:
        if aa is None:
            self._dict.remove_item(_AA)
            return
        self._dict.set_item(
            _AA, _as_cos_dictionary(aa, "set_additional_actions")
        )

    def has_additional_actions(self) -> bool:
        """Predicate: is a parsable ``/AA`` additional-actions dictionary
        present?

        No upstream equivalent.
        """
        value = self._dict.get_dictionary_object(_AA)
        return isinstance(value, COSDictionary)

    def clear_additional_actions(self) -> None:
        """Remove the ``/AA`` additional-actions dictionary, if present."""
        self._dict.remove_item(_AA)

    # Upstream ``PDAnnotationWidget`` exposes the ``/AA`` field through the
    # shorter ``getActions``/``setActions`` pair. Mirror that naming on
    # ``PDAnnotationScreen`` since both annotations carry the same trigger-
    # event additional-action dictionary.

    def get_actions(self) -> PDAnnotationAdditionalActions | None:
        """Alias for :meth:`get_additional_actions` matching upstream Widget."""
        return self.get_additional_actions()

    def set_actions(
        self, actions: PDAnnotationAdditionalActions | COSDictionary | None
    ) -> None:
        """Alias for :meth:`set_additional_actions` matching upstream Widget."""
        self.set_additional_actions(actions)


__all__ = ["PDAnnotationScreen"]
