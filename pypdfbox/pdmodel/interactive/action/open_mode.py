from __future__ import annotations

from enum import Enum


class OpenMode(Enum):
    """Tri-state for the ``/NewWindow`` entry on launch / GoToR / GoToE actions.

    Mirrors upstream Apache PDFBox ``org.apache.pdfbox.pdmodel.interactive.
    action.OpenMode`` (PDF 32000-1 §12.6.4). ``/NewWindow`` is an *optional*
    boolean — its absence (``USER_PREFERENCE``) is semantically distinct from
    an explicit ``False`` (``SAME_WINDOW``), because absence defers to the
    viewer application's user preference.
    """

    #: Entry absent — viewer falls back to user preference.
    USER_PREFERENCE = "user_preference"
    #: ``/NewWindow false`` — replace the current document in the same window.
    SAME_WINDOW = "same_window"
    #: ``/NewWindow true`` — open the destination in a new window.
    NEW_WINDOW = "new_window"


__all__ = ["OpenMode"]
