from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName

from .pd_action import PDAction

_URI: COSName = COSName.get_pdf_name("URI")
_IS_MAP: COSName = COSName.get_pdf_name("IsMap")


class PDActionURI(PDAction):
    """URI action. Mirrors PDFBox ``PDActionURI``."""

    SUB_TYPE = "URI"

    def __init__(self, action: COSDictionary | None = None) -> None:
        super().__init__(action, None if action is not None else self.SUB_TYPE)

    def get_uri(self) -> str | None:
        return self._action.get_string(_URI)

    def set_uri(self, uri: str | None) -> None:
        self._action.set_string(_URI, uri)

    def should_track_mouse_position(self) -> bool:
        return self._action.get_boolean(_IS_MAP, False)

    def set_track_mouse_position(self, value: bool) -> None:
        self._action.set_boolean(_IS_MAP, value)

    # Aliases mirroring the raw PDF dictionary entry name (`/IsMap`).
    def get_is_map(self) -> bool:
        """Return ``/IsMap``. Defaults to ``False`` when absent. Synonym of
        :meth:`should_track_mouse_position` matching the dictionary key
        name verbatim."""
        return self._action.get_boolean(_IS_MAP, False)

    def set_is_map(self, value: bool) -> None:
        """Set ``/IsMap``. Synonym of :meth:`set_track_mouse_position`."""
        self._action.set_boolean(_IS_MAP, value)


__all__ = ["PDActionURI"]
