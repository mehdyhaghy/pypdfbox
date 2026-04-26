from __future__ import annotations

from pypdfbox.cos import COSBase, COSDictionary, COSName

from .pd_media_clip import PDMediaClip

_S: COSName = COSName.get_pdf_name("S")
_D: COSName = COSName.get_pdf_name("D")
_CT: COSName = COSName.get_pdf_name("CT")


class PDMediaClipData(PDMediaClip):
    """``/MediaClip`` of subtype ``/MCD`` (Media Clip Data).

    Mirrors PDFBox ``PDMediaClipData`` — lite surface. Encoding/transmission
    sub-dictionaries are exposed as raw COS for now."""

    SUB_TYPE = "MCD"

    def __init__(self, dictionary: COSDictionary | None = None) -> None:
        super().__init__(dictionary)
        if dictionary is None:
            self._dict.set_name(_S, self.SUB_TYPE)

    def get_d(self) -> COSBase | None:
        return self._dict.get_dictionary_object(_D)

    def set_d(self, data: COSBase | None) -> None:
        if data is None:
            self._dict.remove_item(_D)
            return
        self._dict.set_item(_D, data)

    def get_ct(self) -> str | None:
        return self._dict.get_string(_CT)

    def set_ct(self, ct: str | None) -> None:
        self._dict.set_string(_CT, ct)


__all__ = ["PDMediaClipData"]
