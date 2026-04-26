from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName

from .pd_action import PDAction

_JS: COSName = COSName.get_pdf_name("JS")


class PDActionJavaScript(PDAction):
    """JavaScript action. Mirrors PDFBox ``PDActionJavaScript`` lite surface."""

    SUB_TYPE = "JavaScript"

    def __init__(self, action: COSDictionary | None = None) -> None:
        super().__init__(action, None if action is not None else self.SUB_TYPE)

    def get_action(self) -> str | None:
        return self._action.get_string(_JS)

    def set_action(self, javascript: str | None) -> None:
        self._action.set_string(_JS, javascript)


__all__ = ["PDActionJavaScript"]
