from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName, COSString

from .pd_action import PDAction

_URI: COSName = COSName.get_pdf_name("URI")
_IS_MAP: COSName = COSName.get_pdf_name("IsMap")


class PDActionURI(PDAction):
    """URI action. Mirrors PDFBox ``PDActionURI``."""

    SUB_TYPE = "URI"

    def __init__(self, action: COSDictionary | None = None) -> None:
        super().__init__(action, None if action is not None else self.SUB_TYPE)

    def get_uri(self) -> str | None:
        """Return ``/URI`` decoded per upstream ``PDActionURI.getURI``: UTF-16
        when a BOM is present, otherwise UTF-8 (not PDFDocEncoding). Returns
        ``None`` when the entry is absent or not a ``COSString``.

        PDF 32000-1 §12.6.4.7 specifies the entry should be 7-bit ASCII;
        upstream additionally tolerates UTF-8 / UTF-16 since real-world
        producers stray from the spec."""
        base = self._action.get_dictionary_object(_URI)
        if not isinstance(base, COSString):
            return None
        raw = base.get_bytes()
        if len(raw) >= 2:
            b0, b1 = raw[0], raw[1]
            # UTF-16 BE / LE BOM — defer to COSString.get_string() which
            # already strips the BOM and decodes accordingly.
            if (b0 == 0xFE and b1 == 0xFF) or (b0 == 0xFF and b1 == 0xFE):
                return base.get_string()
        return raw.decode("utf-8", errors="replace")

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
