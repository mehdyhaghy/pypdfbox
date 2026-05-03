from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos import COSBase, COSBoolean, COSDictionary, COSName

from .pd_annotation import PDAnnotation

if TYPE_CHECKING:
    from .pd_annotation_markup import PDAnnotationMarkup

_OPEN: COSName = COSName.get_pdf_name("Open")
_PARENT: COSName = COSName.get_pdf_name("Parent")
_P: COSName = COSName.get_pdf_name("P")


class PDAnnotationPopup(PDAnnotation):
    """
    Popup annotation — ``/Subtype /Popup``. Mirrors
    ``org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationPopup``.

    Displays text in a pop-up window for entry and editing — typically
    associated with a parent markup annotation through ``/Parent``
    (PDF 32000-1:2008 §12.5.6.14).
    """

    SUB_TYPE: str = "Popup"

    def __init__(self, annotation_dict: COSDictionary | None = None) -> None:
        super().__init__(annotation_dict)
        if annotation_dict is None:
            self._set_subtype(self.SUB_TYPE)

    # ---------- /Open ----------

    def get_open(self) -> bool:
        """Default is ``False`` per spec (closed by default)."""
        return self._dict.get_boolean(_OPEN, False)

    def is_open(self) -> bool:
        """Predicate alias for :meth:`get_open` matching the
        ``isXxx`` style used elsewhere in pypdfbox annotations."""
        return self.get_open()

    def set_open(self, value: bool) -> None:
        self._dict.set_item(_OPEN, COSBoolean.get(value))

    # ---------- /Parent (also accepts /P for parser tolerance) ----------

    def get_parent(self) -> COSBase | None:
        """Return the raw parent COS object.

        Mirrors upstream which falls back to ``/P`` when ``/Parent`` is
        absent (``PDAnnotationPopup.getParent`` calls
        ``getDictionaryObject(COSName.PARENT, COSName.P)``).
        """
        value = self._dict.get_dictionary_object(_PARENT)
        if value is None:
            value = self._dict.get_dictionary_object(_P)
        return value

    def get_parent_markup(self) -> PDAnnotationMarkup | None:
        """Typed accessor returning the parent annotation as
        :class:`PDAnnotationMarkup` when the resolved parent is a markup
        annotation dictionary.

        Returns ``None`` when ``/Parent`` (or fallback ``/P``) is absent,
        not a dictionary, or resolves to a non-markup annotation subtype —
        matching upstream's defensive cast (it returns ``null`` when the
        parent's runtime type is not ``PDAnnotationMarkup``).
        """
        from .pd_annotation_markup import PDAnnotationMarkup

        parent = self.get_parent()
        if not isinstance(parent, COSDictionary):
            return None
        ann = PDAnnotation.create(parent)
        if isinstance(ann, PDAnnotationMarkup):
            return ann
        return None

    def set_parent(self, parent: COSBase | None) -> None:
        if parent is None:
            self._dict.remove_item(_PARENT)
            return
        self._dict.set_item(
            _PARENT,
            parent.get_cos_object() if hasattr(parent, "get_cos_object") else parent,
        )


__all__ = ["PDAnnotationPopup"]
