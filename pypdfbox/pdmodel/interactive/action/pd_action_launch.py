from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName

from .pd_action import PDAction

_F: COSName = COSName.get_pdf_name("F")


class PDActionLaunch(PDAction):
    """Launch action. Mirrors PDFBox ``PDActionLaunch`` lite surface."""

    SUB_TYPE = "Launch"

    def __init__(self, action: COSDictionary | None = None) -> None:
        super().__init__(action, None if action is not None else self.SUB_TYPE)

    def get_file(self) -> str | None:
        return self._action.get_string(_F)

    def set_file(self, file_name: str | None) -> None:
        self._action.set_string(_F, file_name)


__all__ = ["PDActionLaunch"]
