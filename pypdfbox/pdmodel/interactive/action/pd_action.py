from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName

_TYPE: COSName = COSName.TYPE  # type: ignore[attr-defined]
_ACTION: COSName = COSName.get_pdf_name("Action")
_S: COSName = COSName.get_pdf_name("S")


class PDAction:
    """Base action wrapper. Mirrors PDFBox ``PDAction``."""

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
        from .pd_action_go_to import PDActionGoTo
        from .pd_action_java_script import PDActionJavaScript
        from .pd_action_launch import PDActionLaunch
        from .pd_action_named import PDActionNamed
        from .pd_action_remote_go_to import PDActionRemoteGoTo
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
        return PDActionUnknown(action)

    def get_cos_object(self) -> COSDictionary:
        return self._action

    def get_sub_type(self) -> str | None:
        return self._action.get_name(_S)

    def set_sub_type(self, sub_type: str) -> None:
        self._action.set_name(_S, sub_type)


__all__ = ["PDAction"]
