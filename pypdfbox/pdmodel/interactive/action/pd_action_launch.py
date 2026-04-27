from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.common.filespecification.pd_file_specification import (
    PDFileSpecification,
)

from .pd_action import PDAction

_F: COSName = COSName.get_pdf_name("F")
_D: COSName = COSName.D  # type: ignore[attr-defined]
_O: COSName = COSName.get_pdf_name("O")
_P: COSName = COSName.get_pdf_name("P")
_NEW_WINDOW: COSName = COSName.get_pdf_name("NewWindow")
_WIN: COSName = COSName.get_pdf_name("Win")


class PDActionLaunch(PDAction):
    """Launch action. Mirrors PDFBox ``PDActionLaunch``.

    PDF 32000-1 §12.6.4.5 Table 196 (Launch action) + Table 197
    (WinLaunchParameters)."""

    SUB_TYPE = "Launch"

    def __init__(self, action: COSDictionary | None = None) -> None:
        super().__init__(action, None if action is not None else self.SUB_TYPE)

    # /F — file specification of the application to launch / document to open.
    def get_file(self) -> PDFileSpecification | None:
        return PDFileSpecification.create_fs(self._action.get_dictionary_object(_F))

    def set_file(self, fs: PDFileSpecification | None) -> None:
        if fs is None:
            self._action.remove_item(_F)
            return
        self._action.set_item(_F, fs.get_cos_object())

    # /D — Solaris/Mac launch command (text string).
    def get_d(self) -> str | None:
        return self._action.get_string(_D)

    def set_d(self, value: str | None) -> None:
        self._action.set_string(_D, value)

    # /O — operation to perform (Win only); usually "open" or "print".
    def get_o(self) -> str | None:
        return self._action.get_string(_O)

    def set_o(self, value: str | None) -> None:
        self._action.set_string(_O, value)

    # /P — parameters passed to the application (Win only).
    def get_p(self) -> str | None:
        return self._action.get_string(_P)

    def set_p(self, value: str | None) -> None:
        self._action.set_string(_P, value)

    # /NewWindow — boolean (PDF 1.2). Defaults to False when absent.
    def get_open_in_new_window(self) -> bool:
        return self._action.get_boolean(_NEW_WINDOW, False)

    def set_open_in_new_window(self, value: bool) -> None:
        self._action.set_boolean(_NEW_WINDOW, value)

    # /Win — Windows launch parameters dict (Table 197). Typed
    # ``PDWindowsLaunchParams`` wrapper is deferred — see CHANGES.md.
    def get_win_launch_params(self) -> COSDictionary | None:
        v = self._action.get_dictionary_object(_WIN)
        if isinstance(v, COSDictionary):
            return v
        return None

    def set_win_launch_params(self, value: COSDictionary | None) -> None:
        if value is None:
            self._action.remove_item(_WIN)
            return
        self._action.set_item(_WIN, value)


__all__ = ["PDActionLaunch"]
