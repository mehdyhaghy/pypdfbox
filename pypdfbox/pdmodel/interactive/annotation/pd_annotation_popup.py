from __future__ import annotations

from pypdfbox.cos import COSBase, COSBoolean, COSDictionary, COSName

from .pd_annotation import PDAnnotation

_OPEN: COSName = COSName.get_pdf_name("Open")
_PARENT: COSName = COSName.get_pdf_name("Parent")


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

    def set_open(self, value: bool) -> None:
        self._dict.set_item(_OPEN, COSBoolean.get(value))

    # ---------- /Parent ----------

    def get_parent(self) -> COSBase | None:
        """Cluster #5 lite returns the raw ``/Parent`` COS object. The
        typed parent annotation (``PDAnnotationMarkup``) is deferred — see
        ``CHANGES.md``."""
        return self._dict.get_dictionary_object(_PARENT)

    def set_parent(self, parent: COSBase | None) -> None:
        if parent is None:
            self._dict.remove_item(_PARENT)
            return
        self._dict.set_item(
            _PARENT,
            parent.get_cos_object() if hasattr(parent, "get_cos_object") else parent,
        )


__all__ = ["PDAnnotationPopup"]
