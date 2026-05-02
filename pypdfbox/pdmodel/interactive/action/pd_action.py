from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName

_TYPE: COSName = COSName.TYPE  # type: ignore[attr-defined]
_ACTION: COSName = COSName.get_pdf_name("Action")
_S: COSName = COSName.get_pdf_name("S")
_NEXT: COSName = COSName.get_pdf_name("Next")


class PDAction:
    """Base action wrapper. Mirrors PDFBox ``PDAction``."""

    #: Type entry value for an action dictionary (PDF 32000-1 §12.6.2).
    TYPE: str = "Action"

    def __init__(
        self,
        action: COSDictionary | None = None,
        sub_type: str | None = None,
    ) -> None:
        self._action = action if action is not None else COSDictionary()
        if self._action.get_dictionary_object(_TYPE) is None:
            self._action.set_item(_TYPE, _ACTION)
        if sub_type is not None:
            self.set_sub_type(sub_type)

    @staticmethod
    def create(action: COSDictionary | None) -> PDAction | None:
        from .pd_action_embedded_go_to import PDActionEmbeddedGoTo
        from .pd_action_go_to import PDActionGoTo
        from .pd_action_go_to_3d_view import PDActionGoTo3DView
        from .pd_action_go_to_dp import PDActionGoToDp
        from .pd_action_hide import PDActionHide
        from .pd_action_import_data import PDActionImportData
        from .pd_action_java_script import PDActionJavaScript
        from .pd_action_launch import PDActionLaunch
        from .pd_action_movie import PDActionMovie
        from .pd_action_named import PDActionNamed
        from .pd_action_remote_go_to import PDActionRemoteGoTo
        from .pd_action_rendition import PDActionRendition
        from .pd_action_reset_form import PDActionResetForm
        from .pd_action_rich_media_execute import PDActionRichMediaExecute
        from .pd_action_set_ocg_state import PDActionSetOCGState
        from .pd_action_sound import PDActionSound
        from .pd_action_submit_form import PDActionSubmitForm
        from .pd_action_thread import PDActionThread
        from .pd_action_transition import PDActionTransition
        from .pd_action_unknown import PDActionUnknown
        from .pd_action_uri import PDActionURI

        if action is None:
            return None
        if not isinstance(action, COSDictionary):
            raise TypeError(f"PDAction.create expects COSDictionary, got {type(action).__name__}")
        sub_type = action.get_name(_S)
        if sub_type == PDActionGoTo.SUB_TYPE:
            return PDActionGoTo(action)
        if sub_type == PDActionURI.SUB_TYPE:
            return PDActionURI(action)
        if sub_type == PDActionNamed.SUB_TYPE:
            return PDActionNamed(action)
        if sub_type == PDActionLaunch.SUB_TYPE:
            return PDActionLaunch(action)
        if sub_type == PDActionRemoteGoTo.SUB_TYPE:
            return PDActionRemoteGoTo(action)
        if sub_type == PDActionJavaScript.SUB_TYPE:
            return PDActionJavaScript(action)
        if sub_type == PDActionSubmitForm.SUB_TYPE:
            return PDActionSubmitForm(action)
        if sub_type == PDActionResetForm.SUB_TYPE:
            return PDActionResetForm(action)
        if sub_type == PDActionImportData.SUB_TYPE:
            return PDActionImportData(action)
        if sub_type == PDActionHide.SUB_TYPE:
            return PDActionHide(action)
        if sub_type == PDActionThread.SUB_TYPE:
            return PDActionThread(action)
        if sub_type == PDActionSound.SUB_TYPE:
            return PDActionSound(action)
        if sub_type == PDActionMovie.SUB_TYPE:
            return PDActionMovie(action)
        if sub_type == PDActionRendition.SUB_TYPE:
            return PDActionRendition(action)
        if sub_type == PDActionTransition.SUB_TYPE:
            return PDActionTransition(action)
        if sub_type == PDActionEmbeddedGoTo.SUB_TYPE:
            return PDActionEmbeddedGoTo(action)
        if sub_type == PDActionSetOCGState.SUB_TYPE:
            return PDActionSetOCGState(action)
        if sub_type == PDActionGoToDp.SUB_TYPE:
            return PDActionGoToDp(action)
        if sub_type == PDActionGoTo3DView.SUB_TYPE:
            return PDActionGoTo3DView(action)
        if sub_type == PDActionRichMediaExecute.SUB_TYPE:
            return PDActionRichMediaExecute(action)
        return PDActionUnknown(action)

    def get_cos_object(self) -> COSDictionary:
        return self._action

    def get_type(self) -> str | None:
        """Return the ``/Type`` entry of the action dictionary.

        If present in a conforming document this is always ``"Action"``
        (PDF 32000-1 §12.6.2 Table 192). Mirrors upstream
        ``PDAction.getType()``.
        """
        return self._action.get_name(_TYPE)

    def set_type(self, type_value: str) -> None:
        """Set the ``/Type`` entry of the action dictionary.

        Protected in upstream Java; exposed here as a public method since
        Python has no equivalent visibility modifier. Conforming documents
        should always pass ``"Action"``.
        """
        self._action.set_name(_TYPE, type_value)

    def get_sub_type(self) -> str | None:
        return self._action.get_name(_S)

    def set_sub_type(self, sub_type: str) -> None:
        self._action.set_name(_S, sub_type)

    def get_next(self) -> list[PDAction] | None:
        """Return the ``/Next`` action(s) to be performed after this one.

        ``/Next`` may be a single action dictionary or an array of action
        dictionaries (PDF 32000-1 §12.6.2 Table 192). Returns ``None`` if
        no ``/Next`` entry exists. Mirrors upstream ``PDAction.getNext()``.
        """
        nxt = self._action.get_dictionary_object(_NEXT)
        if nxt is None:
            return None
        if isinstance(nxt, COSDictionary):
            single = PDAction.create(nxt)
            return [single] if single is not None else []
        if isinstance(nxt, COSArray):
            actions: list[PDAction] = []
            for i in range(nxt.size()):
                entry = nxt.get_object(i)
                if isinstance(entry, COSDictionary):
                    pd = PDAction.create(entry)
                    if pd is not None:
                        actions.append(pd)
            return actions
        return None

    def set_next(self, next_actions: list[PDAction] | None) -> None:
        """Set the ``/Next`` action(s) to be performed after this one.

        Stored as a ``COSArray`` of action dictionaries. ``None`` removes
        the entry. Mirrors upstream ``PDAction.setNext(List<PDAction>)``.
        """
        if next_actions is None:
            self._action.remove_item(_NEXT)
            return
        array = COSArray()
        for entry in next_actions:
            array.add(entry.get_cos_object())
        self._action.set_item(_NEXT, array)


__all__ = ["PDAction"]
