from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName

from .pd_media_clip import PDMediaClip
from .pd_media_play_parameters import PDMediaPlayParameters
from .pd_rendition import PDRendition

_S: COSName = COSName.get_pdf_name("S")
_C: COSName = COSName.get_pdf_name("C")
_P: COSName = COSName.get_pdf_name("P")


class PDMediaRendition(PDRendition):
    """Rendition of subtype ``/MR`` (media rendition).

    Mirrors PDFBox ``PDMediaRendition``."""

    SUB_TYPE = "MR"

    def __init__(self, dictionary: COSDictionary | None = None) -> None:
        super().__init__(dictionary)
        if dictionary is None:
            self._dict.set_name(_S, self.SUB_TYPE)

    def get_c(self) -> PDMediaClip | None:
        c = self._dict.get_dictionary_object(_C)
        if isinstance(c, COSDictionary):
            return PDMediaClip.create(c)
        return None

    def set_c(self, clip: PDMediaClip | None) -> None:
        if clip is None:
            self._dict.remove_item(_C)
            return
        self._dict.set_item(_C, clip.get_cos_object())

    def get_p(self) -> PDMediaPlayParameters | None:
        p = self._dict.get_dictionary_object(_P)
        if isinstance(p, COSDictionary):
            return PDMediaPlayParameters(p)
        return None

    def set_p(self, params: PDMediaPlayParameters | None) -> None:
        if params is None:
            self._dict.remove_item(_P)
            return
        self._dict.set_item(_P, params.get_cos_object())


__all__ = ["PDMediaRendition"]
