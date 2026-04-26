from __future__ import annotations

from pypdfbox.cos import COSBase, COSDictionary, COSName

from .pd_action import PDAction

_ANNOTATION: COSName = COSName.get_pdf_name("Annotation")
_T: COSName = COSName.get_pdf_name("T")
_OPERATION: COSName = COSName.get_pdf_name("Operation")


class PDActionMovie(PDAction):
    """Movie action. Mirrors PDFBox ``PDActionMovie`` lite surface.

    The ``/Annotation`` entry is exposed as a raw ``COSBase`` for now; a typed
    ``PDAnnotationMovie`` wrapper is deferred."""

    SUB_TYPE = "Movie"

    def __init__(self, action: COSDictionary | None = None) -> None:
        super().__init__(action, None if action is not None else self.SUB_TYPE)

    def get_annotation(self) -> COSBase | None:
        return self._action.get_dictionary_object(_ANNOTATION)

    def set_annotation(self, annotation: COSBase | None) -> None:
        if annotation is None:
            self._action.remove_item(_ANNOTATION)
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
