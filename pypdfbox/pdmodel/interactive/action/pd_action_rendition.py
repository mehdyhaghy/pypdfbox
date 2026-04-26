from __future__ import annotations

from pypdfbox.cos import COSBase, COSDictionary, COSName

from .pd_action import PDAction

_AN: COSName = COSName.get_pdf_name("AN")
_OP: COSName = COSName.get_pdf_name("OP")
_JS: COSName = COSName.get_pdf_name("JS")
_R: COSName = COSName.get_pdf_name("R")


class PDActionRendition(PDAction):
    """Rendition action. Mirrors PDFBox ``PDActionRendition`` lite surface.

    ``/AN`` (annotation widget reference) and ``/R`` (rendition dictionary)
    are exposed as raw ``COSBase`` for now; typed wrappers are deferred."""

    SUB_TYPE = "Rendition"

    def __init__(self, action: COSDictionary | None = None) -> None:
        super().__init__(action, None if action is not None else self.SUB_TYPE)

    def get_an(self) -> COSBase | None:
        return self._action.get_dictionary_object(_AN)

    def set_an(self, an: COSBase | None) -> None:
        if an is None:
            self._action.remove_item(_AN)
            return
        self._action.set_item(_AN, an)

    def get_op(self) -> int:
        return self._action.get_int(_OP)

    def set_op(self, op: int) -> None:
        self._action.set_int(_OP, op)

    def get_js(self) -> str | None:
        return self._action.get_string(_JS)

    def set_js(self, js: str | None) -> None:
        self._action.set_string(_JS, js)

    def get_r(self) -> COSBase | None:
        return self._action.get_dictionary_object(_R)

    def set_r(self, r: COSBase | None) -> None:
        if r is None:
            self._action.remove_item(_R)
            return
        self._action.set_item(_R, r)


__all__ = ["PDActionRendition"]
