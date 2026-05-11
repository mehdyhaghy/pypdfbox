"""Factory that maps an action dictionary's ``/S`` to a ``PDAction`` subclass.

Mirrors ``org.apache.pdfbox.pdmodel.interactive.action.PDActionFactory``
(PDFBox 3.0, ``pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/
action/PDActionFactory.java``).
"""

from __future__ import annotations

from pypdfbox.cos.cos_dictionary import COSDictionary
from pypdfbox.cos.cos_name import COSName
from pypdfbox.pdmodel.interactive.action.pd_action import PDAction
from pypdfbox.pdmodel.interactive.action.pd_action_embedded_go_to import (
    PDActionEmbeddedGoTo,
)
from pypdfbox.pdmodel.interactive.action.pd_action_go_to import PDActionGoTo
from pypdfbox.pdmodel.interactive.action.pd_action_hide import PDActionHide
from pypdfbox.pdmodel.interactive.action.pd_action_import_data import PDActionImportData
from pypdfbox.pdmodel.interactive.action.pd_action_java_script import PDActionJavaScript
from pypdfbox.pdmodel.interactive.action.pd_action_launch import PDActionLaunch
from pypdfbox.pdmodel.interactive.action.pd_action_movie import PDActionMovie
from pypdfbox.pdmodel.interactive.action.pd_action_named import PDActionNamed
from pypdfbox.pdmodel.interactive.action.pd_action_remote_go_to import PDActionRemoteGoTo
from pypdfbox.pdmodel.interactive.action.pd_action_reset_form import PDActionResetForm
from pypdfbox.pdmodel.interactive.action.pd_action_sound import PDActionSound
from pypdfbox.pdmodel.interactive.action.pd_action_submit_form import PDActionSubmitForm
from pypdfbox.pdmodel.interactive.action.pd_action_thread import PDActionThread
from pypdfbox.pdmodel.interactive.action.pd_action_uri import PDActionURI


class PDActionFactory:
    """Static-only factory mirroring upstream's ``createAction``."""

    def __init__(self) -> None:  # pragma: no cover
        raise TypeError("PDActionFactory is a utility class")

    @staticmethod
    def create_action(action: COSDictionary | None) -> PDAction | None:
        """Build the right ``PDAction`` subclass for ``action``'s subtype."""
        if action is None:
            return None
        s_type = action.get_name_as_string(COSName.get_pdf_name("S"))
        if s_type is None:
            return None
        mapping = {
            PDActionJavaScript.SUB_TYPE: PDActionJavaScript,
            PDActionGoTo.SUB_TYPE: PDActionGoTo,
            PDActionLaunch.SUB_TYPE: PDActionLaunch,
            PDActionRemoteGoTo.SUB_TYPE: PDActionRemoteGoTo,
            PDActionURI.SUB_TYPE: PDActionURI,
            PDActionNamed.SUB_TYPE: PDActionNamed,
            PDActionSound.SUB_TYPE: PDActionSound,
            PDActionMovie.SUB_TYPE: PDActionMovie,
            PDActionImportData.SUB_TYPE: PDActionImportData,
            PDActionResetForm.SUB_TYPE: PDActionResetForm,
            PDActionHide.SUB_TYPE: PDActionHide,
            PDActionSubmitForm.SUB_TYPE: PDActionSubmitForm,
            PDActionThread.SUB_TYPE: PDActionThread,
            PDActionEmbeddedGoTo.SUB_TYPE: PDActionEmbeddedGoTo,
        }
        cls = mapping.get(s_type)
        if cls is None:
            return None
        return cls(action)


__all__ = ["PDActionFactory"]
