from __future__ import annotations

from pypdfbox.cos import COSBase, COSDictionary, COSName, COSNull, COSObject

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
    def create(base: COSBase | None) -> PDMediaClip | None:
        from .pd_media_clip_data import PDMediaClipData
        from .pd_media_clip_section import PDMediaClipSection

        seen_refs: set[int] = set()
        while isinstance(base, COSObject):
            ref_id = id(base)
            if ref_id in seen_refs:
                return None
            seen_refs.add(ref_id)
            base = base.get_object()
        if base is None or base is COSNull.NULL:
            return None
        if not isinstance(base, COSDictionary):
            raise TypeError(
                f"PDMediaClip.create expects COSDictionary, got {type(base).__name__}"
            )
        sub_type = base.get_string(_S)
        if sub_type == PDMediaClipData.SUB_TYPE:
            return PDMediaClipData(base)
        if sub_type == PDMediaClipSection.SUB_TYPE:
            return PDMediaClipSection(base)
        return None

    def get_cos_object(self) -> COSDictionary:
        return self._dict

    def get_subtype(self) -> str | None:
        return self._dict.get_string(_S)

    def get_n(self) -> str | None:
        return self._dict.get_string(_N)

    def set_n(self, name: str | None) -> None:
        self._dict.set_string(_N, name)


__all__ = ["PDMediaClip"]
