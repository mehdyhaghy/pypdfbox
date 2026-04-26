from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName

_TYPE: COSName = COSName.TYPE  # type: ignore[attr-defined]
_MEDIA_CLIP: COSName = COSName.get_pdf_name("MediaClip")
_S: COSName = COSName.get_pdf_name("S")
_N: COSName = COSName.get_pdf_name("N")


class PDMediaClip:
    """Abstract base for ``/MediaClip`` (``/MC``) dictionaries.

    Mirrors PDFBox ``PDMediaClip``. Use :meth:`create` to dispatch on ``/S``."""

    def __init__(self, dictionary: COSDictionary | None = None) -> None:
        self._dict = dictionary if dictionary is not None else COSDictionary()
        if self._dict.get_dictionary_object(_TYPE) is None:
            self._dict.set_item(_TYPE, _MEDIA_CLIP)

    @staticmethod
    def create(dictionary: COSDictionary | None) -> PDMediaClip | None:
        from .pd_media_clip_data import PDMediaClipData
        from .pd_media_clip_section import PDMediaClipSection

        if dictionary is None:
            return None
        if not isinstance(dictionary, COSDictionary):
            raise TypeError(
                f"PDMediaClip.create expects COSDictionary, got {type(dictionary).__name__}"
            )
        sub_type = dictionary.get_name(_S)
        if sub_type == PDMediaClipData.SUB_TYPE:
            return PDMediaClipData(dictionary)
        if sub_type == PDMediaClipSection.SUB_TYPE:
            return PDMediaClipSection(dictionary)
        return None

    def get_cos_object(self) -> COSDictionary:
        return self._dict

    def get_subtype(self) -> str | None:
        return self._dict.get_name(_S)

    def get_n(self) -> str | None:
        return self._dict.get_string(_N)

    def set_n(self, name: str | None) -> None:
        self._dict.set_string(_N, name)


__all__ = ["PDMediaClip"]
