from __future__ import annotations

from pypdfbox.cos import COSBase, COSDictionary, COSName
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_movie import (
    PDAnnotationMovie,
)

from .pd_action import PDAction

_ANNOTATION: COSName = COSName.get_pdf_name("Annotation")
_T: COSName = COSName.get_pdf_name("T")
_OPERATION: COSName = COSName.get_pdf_name("Operation")


class PDActionMovie(PDAction):
    """Movie action. Mirrors PDFBox ``PDActionMovie``.

    The ``/Annotation`` entry is exposed both as a raw ``COSBase`` via
    :meth:`get_annotation_dictionary` (legacy back-compat) and as a
    typed :class:`PDAnnotationMovie` via :meth:`get_annotation`."""

    SUB_TYPE = "Movie"

    def __init__(self, action: COSDictionary | None = None) -> None:
        super().__init__(action, None if action is not None else self.SUB_TYPE)

    def get_annotation_dictionary(self) -> COSBase | None:
        """Return the raw ``/Annotation`` entry. Back-compat surface — new
        code should prefer :meth:`get_annotation` for the typed wrapper."""
        return self._action.get_dictionary_object(_ANNOTATION)

    def get_annotation(self) -> PDAnnotationMovie | None:
        """Return ``/Annotation`` as a typed :class:`PDAnnotationMovie`, or
        ``None`` when the entry is absent or not a dictionary."""
        entry = self._action.get_dictionary_object(_ANNOTATION)
        if isinstance(entry, COSDictionary):
            return PDAnnotationMovie(entry)
        return None

    def set_annotation(
        self, annotation: PDAnnotationMovie | COSBase | None
    ) -> None:
        """Replace ``/Annotation``. Accepts ``None`` (removes the entry),
        a :class:`PDAnnotationMovie` (stores its underlying COSDictionary),
        or a raw ``COSBase`` (stored as-is for back-compat)."""
        if annotation is None:
            self._action.remove_item(_ANNOTATION)
            return
        if isinstance(annotation, PDAnnotationMovie):
            self._action.set_item(_ANNOTATION, annotation.get_cos_object())
            return
        self._action.set_item(_ANNOTATION, annotation)

    def get_t(self) -> str | None:
        return self._action.get_string(_T)

    def set_t(self, title: str | None) -> None:
        self._action.set_string(_T, title)

    def get_operation(self) -> str | None:
        return self._action.get_name(_OPERATION)

    def set_operation(self, operation: str | None) -> None:
        if operation is None:
            self._action.remove_item(_OPERATION)
            return
        self._action.set_name(_OPERATION, operation)


__all__ = ["PDActionMovie"]
