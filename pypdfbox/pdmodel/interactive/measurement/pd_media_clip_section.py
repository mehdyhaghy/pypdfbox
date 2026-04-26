from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName

from .pd_media_clip import PDMediaClip

_S: COSName = COSName.get_pdf_name("S")
_D: COSName = COSName.get_pdf_name("D")


class PDMediaClipSection(PDMediaClip):
    """``/MediaClip`` of subtype ``/MCS`` (Media Clip Section).

    Mirrors PDFBox ``PDMediaClipSection`` — lite surface."""

    SUB_TYPE = "MCS"

    def __init__(self, dictionary: COSDictionary | None = None) -> None:
        super().__init__(dictionary)
        if dictionary is None:
            self._dict.set_name(_S, self.SUB_TYPE)

    def get_d(self) -> PDMediaClip | None:
        d = self._dict.get_dictionary_object(_D)
        if isinstance(d, COSDictionary):
            return PDMediaClip.create(d)
        return None

    def set_d(self, clip: PDMediaClip | None) -> None:
        if clip is None:
            self._dict.remove_item(_D)
            return
        self._dict.set_item(_D, clip.get_cos_object())


__all__ = ["PDMediaClipSection"]
