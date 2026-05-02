from __future__ import annotations

from pypdfbox.cos import COSArray, COSBase, COSBoolean, COSDictionary, COSName, COSString
from pypdfbox.pdmodel.common.filespecification.pd_file_specification import (
    PDFileSpecification,
)
from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_destination import (
    PDDestination,
)

from .open_mode import OpenMode
from .pd_action import PDAction

_D: COSName = COSName.D  # type: ignore[attr-defined]
_F: COSName = COSName.get_pdf_name("F")
_NEW_WINDOW: COSName = COSName.get_pdf_name("NewWindow")


class PDActionRemoteGoTo(PDAction):
    """Remote GoTo action. Mirrors PDFBox ``PDActionRemoteGoTo``.

    PDF 32000-1 §12.6.4.3 Table 199: ``/F`` references the target document
    (text string or file specification), ``/D`` is the destination within
    that document, and ``/NewWindow`` (PDF 1.2) optionally requests a fresh
    window.
    """

    SUB_TYPE = "GoToR"

    def __init__(self, action: COSDictionary | None = None) -> None:
        super().__init__(action, None if action is not None else self.SUB_TYPE)

    # /F ---------------------------------------------------------------
    def get_file(self) -> str | None:
        """Return ``/F`` as a text string (mirrors upstream ``getF()``).

        For typed file-specification access use :meth:`get_file_specification`.
        """
        return self._action.get_string(_F)

    def set_file(
        self,
        file_name: PDFileSpecification | str | bytes | None,
    ) -> None:
        """Set ``/F``. Accepts a plain string (mirrors upstream ``setF``),
        a :class:`PDFileSpecification` (the entry is then written as the
        file-spec's COS form), or ``None`` to remove the entry."""
        if file_name is None:
            self._action.remove_item(_F)
            return
        if isinstance(file_name, PDFileSpecification):
            self._action.set_item(_F, file_name.get_cos_object())
            return
        self._action.set_string(_F, file_name)

    def get_file_specification(self) -> PDFileSpecification | None:
        """Return ``/F`` as a typed :class:`PDFileSpecification`, dispatching
        on whether the entry is a ``COSString`` (simple) or ``COSDictionary``
        (complex). Returns ``None`` when ``/F`` is absent."""
        return PDFileSpecification.create_fs(self._action.get_dictionary_object(_F))

    def set_file_specification(self, file_spec: PDFileSpecification | None) -> None:
        """Set ``/F`` from a typed :class:`PDFileSpecification`, or remove
        it when ``file_spec`` is ``None``."""
        if file_spec is None:
            self._action.remove_item(_F)
            return
        self._action.set_item(_F, file_spec.get_cos_object())

    # /D ---------------------------------------------------------------
    def get_d(self) -> COSBase | None:
        return self._action.get_dictionary_object(_D)

    def set_d(self, destination: COSBase | None) -> None:
        if destination is None:
            self._action.remove_item(_D)
            return
        self._action.set_item(_D, destination)

    def get_named_destination(self) -> str | None:
        """Return ``/D`` when it is a string-form named destination."""
        d = self._action.get_dictionary_object(_D)
        if isinstance(d, COSString):
            return d.get_string()
        return None

    def get_destination(self) -> PDDestination | str | None:
        """Return ``/D`` dispatched to its appropriate type:

        - ``PDDestination`` instance for explicit page-target arrays
          (``COSArray`` form);
        - ``str`` for named destinations (``COSString`` or ``COSName`` form);
        - ``None`` when ``/D`` is absent.
        """
        d = self._action.get_dictionary_object(_D)
        if d is None:
            return None
        if isinstance(d, COSArray):
            return PDDestination.create(d)
        if isinstance(d, COSString):
            return d.get_string()
        if isinstance(d, COSName):
            return d.get_name()
        return None

    def set_destination(
        self, destination: PDDestination | str | COSBase | None
    ) -> None:
        """Write ``/D`` from a typed :class:`PDDestination`, a named-destination
        string, a raw :class:`COSBase`, or ``None`` (which removes the entry).

        Mirrors upstream ``PDActionRemoteGoTo#setDestination``."""
        if destination is None:
            self._action.remove_item(_D)
            return
        if isinstance(destination, PDDestination):
            self._action.set_item(_D, destination.get_cos_object())
            return
        if isinstance(destination, str):
            self._action.set_string(_D, destination)
            return
        self._action.set_item(_D, destination)

    def set_named_destination(self, name: str | None) -> None:
        if name is None:
            self._action.remove_item(_D)
            return
        self._action.set_string(_D, name)

    # /NewWindow -------------------------------------------------------
    def get_new_window(self) -> bool:
        """Return ``/NewWindow`` (PDF 1.2). Defaults to ``False`` when absent.

        Mirrors upstream ``PDActionRemoteGoTo#shouldOpenInNewWindow`` /
        the ``getNewWindow`` accessor."""
        return self._action.get_boolean(_NEW_WINDOW, False)

    def set_new_window(self, value: bool) -> None:
        """Set ``/NewWindow``."""
        self._action.set_boolean(_NEW_WINDOW, value)

    def should_open_in_new_window(self) -> bool:
        """Alias of :meth:`get_new_window` matching upstream
        ``shouldOpenInNewWindow`` spelling."""
        return self.get_new_window()

    def set_open_in_new_window(self, value: bool | OpenMode | None) -> None:
        """Set ``/NewWindow``. Accepts a plain ``bool``, an :class:`OpenMode`,
        or ``None``; both :attr:`OpenMode.USER_PREFERENCE` and ``None``
        remove the entry (mirrors upstream ``setOpenInNewWindow(null)``
        which falls through to user preference). Mirrors upstream
        ``setOpenInNewWindow(OpenMode)`` while retaining the historical
        bool overload."""
        if value is None:
            self._action.remove_item(_NEW_WINDOW)
            return
        if isinstance(value, OpenMode):
            if value is OpenMode.USER_PREFERENCE:
                self._action.remove_item(_NEW_WINDOW)
                return
            self._action.set_boolean(_NEW_WINDOW, value is OpenMode.NEW_WINDOW)
            return
        self.set_new_window(bool(value))

    def get_open_in_new_window(self) -> OpenMode:
        """Return ``/NewWindow`` as an :class:`OpenMode` tri-state. Mirrors
        upstream ``PDActionRemoteGoTo.getOpenInNewWindow()`` which
        returns ``OpenMode``. ``USER_PREFERENCE`` when the entry is
        absent / non-boolean; ``NEW_WINDOW`` / ``SAME_WINDOW`` for
        explicit ``true`` / ``false``."""
        entry = self._action.get_dictionary_object(_NEW_WINDOW)
        if isinstance(entry, COSBoolean):
            return OpenMode.NEW_WINDOW if entry.get_value() else OpenMode.SAME_WINDOW
        return OpenMode.USER_PREFERENCE

    def is_new_window(self) -> bool:
        """``True`` iff ``/NewWindow`` is explicitly ``true``. Convenience
        predicate paralleling :class:`PDActionEmbeddedGoTo.is_new_window`
        / :class:`PDActionLaunch.is_new_window`; absence yields ``False``."""
        return self.get_open_in_new_window() is OpenMode.NEW_WINDOW


__all__ = ["PDActionRemoteGoTo"]
