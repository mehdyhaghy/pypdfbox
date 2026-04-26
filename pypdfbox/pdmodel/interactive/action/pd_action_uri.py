from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName

from .pd_action import PDAction

_URI: COSName = COSName.get_pdf_name("URI")


class PDActionURI(PDAction):
    """URI action. Mirrors PDFBox ``PDActionURI``."""

    SUB_TYPE = "URI"

    def __init__(self, action: COSDictionary | None = None) -> None:
        super().__init__(action, None if action is not None else self.SUB_TYPE)

    def get_uri(self) -> str | None:
        return self._action.get_string(_URI)

    def set_uri(self, uri: str | None) -> None:
        self._action.set_string(_URI, uri)


__all__ = ["PDActionURI"]
