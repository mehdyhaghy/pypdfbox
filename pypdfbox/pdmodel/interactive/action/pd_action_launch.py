from __future__ import annotations

from pypdfbox.cos import COSBoolean, COSDictionary, COSName
from pypdfbox.pdmodel.common.filespecification.pd_file_specification import (
    PDFileSpecification,
)

from .open_mode import OpenMode
from .pd_action import PDAction
from .pd_windows_launch_params import PDWindowsLaunchParams

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

    # /F as a plain string — upstream ``getF()``/``setF(String)`` surface,
    # kept for callers that work directly with the legacy text-form file
    # specification (PDF 32000-1 §7.11.2 simple form).
    def get_f(self) -> str | None:
        return self._action.get_string(_F)

    def set_f(self, value: str | None) -> None:
        self._action.set_string(_F, value)

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
        """Return ``/NewWindow`` as a bool, defaulting to ``False`` when the
        entry is absent. For the upstream tri-state surface (which
        distinguishes "entry absent" from explicit ``false``) use
        :meth:`get_open_in_new_window_mode`."""
        return self._action.get_boolean(_NEW_WINDOW, False)

    def set_open_in_new_window(self, value: bool | OpenMode) -> None:
        """Set ``/NewWindow``.

        Accepts a plain ``bool`` or an :class:`OpenMode`.
        :attr:`OpenMode.USER_PREFERENCE` removes the entry; ``NEW_WINDOW`` /
        ``SAME_WINDOW`` map to ``True`` / ``False`` respectively."""
        if isinstance(value, OpenMode):
            if value is OpenMode.USER_PREFERENCE:
                self._action.remove_item(_NEW_WINDOW)
                return
            self._action.set_boolean(_NEW_WINDOW, value is OpenMode.NEW_WINDOW)
            return
        self._action.set_boolean(_NEW_WINDOW, bool(value))

    def get_open_in_new_window_mode(self) -> OpenMode:
        """Return ``/NewWindow`` as the upstream :class:`OpenMode` tri-state.

        Mirrors upstream ``PDActionLaunch.getOpenInNewWindow()`` which
        returns ``OpenMode``. ``USER_PREFERENCE`` when the entry is
        absent / non-boolean; ``NEW_WINDOW`` / ``SAME_WINDOW`` for
        explicit ``true`` / ``false``."""
        entry = self._action.get_dictionary_object(_NEW_WINDOW)
        if isinstance(entry, COSBoolean):
            return OpenMode.NEW_WINDOW if entry.get_value() else OpenMode.SAME_WINDOW
        return OpenMode.USER_PREFERENCE

    def is_new_window(self) -> bool:
        """``True`` iff ``/NewWindow`` is explicitly ``true``. Convenience
        predicate; absence yields ``False``."""
        return self.get_open_in_new_window_mode() is OpenMode.NEW_WINDOW

    # /Win — Windows launch parameters dict (Table 197).
    def get_win_launch_params(self) -> PDWindowsLaunchParams | None:
        """Return the typed ``/Win`` sub-dict wrapper, or ``None``.

        Mirrors upstream ``PDActionLaunch#getWinLaunchParams``.
        """
        v = self._action.get_dictionary_object(_WIN)
        if isinstance(v, COSDictionary):
            return PDWindowsLaunchParams(v)
        return None

    def set_win_launch_params(
        self, value: PDWindowsLaunchParams | COSDictionary | None
    ) -> None:
        """Set or clear the ``/Win`` sub-dict.

        Accepts a typed :class:`PDWindowsLaunchParams`, a raw
        :class:`COSDictionary` (for backwards compatibility with code written
        before the typed wrapper existed), or ``None`` to remove the entry.
        """
        if value is None:
            self._action.remove_item(_WIN)
            return
        if isinstance(value, PDWindowsLaunchParams):
            self._action.set_item(_WIN, value.get_cos_object())
            return
        self._action.set_item(_WIN, value)


__all__ = ["PDActionLaunch"]
