from __future__ import annotations

from pypdfbox.cos import COSBase, COSDictionary, COSName, COSNull, COSObject

_TYPE: COSName = COSName.TYPE  # type: ignore[attr-defined]
_RENDITION: COSName = COSName.get_pdf_name("Rendition")
_S: COSName = COSName.get_pdf_name("S")
_N: COSName = COSName.get_pdf_name("N")
_MH: COSName = COSName.get_pdf_name("MH")
_BE: COSName = COSName.get_pdf_name("BE")


class PDRendition:
    """Abstract base for ``/Rendition`` dictionaries.

    Mirrors PDFBox ``PDRendition``. Use :meth:`create` to build a concrete
    subclass from a raw ``COSDictionary`` (dispatches on ``/S``)."""

    def __init__(self, dictionary: COSDictionary | None = None) -> None:
        self._dict = dictionary if dictionary is not None else COSDictionary()
        if self._dict.get_dictionary_object(_TYPE) is None:
            self._dict.set_item(_TYPE, _RENDITION)

    @staticmethod
    def create(base: COSBase | None) -> PDRendition | None:
        from .pd_media_rendition import PDMediaRendition
        from .pd_selector_rendition import PDSelectorRendition

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
                f"PDRendition.create expects COSDictionary, got {type(base).__name__}"
            )
        sub_type = base.get_string(_S)
        if sub_type == PDMediaRendition.SUB_TYPE:
            return PDMediaRendition(base)
        if sub_type == PDSelectorRendition.SUB_TYPE:
            return PDSelectorRendition(base)
        return None

    def get_cos_object(self) -> COSDictionary:
        return self._dict

    def get_subtype(self) -> str | None:
        return self._dict.get_string(_S)

    def get_n(self) -> str | None:
        return self._dict.get_string(_N)

    def set_n(self, name: str | None) -> None:
        self._dict.set_string(_N, name)

    def get_mh(self) -> COSDictionary | None:
        v = self._dict.get_dictionary_object(_MH)
        return v if isinstance(v, COSDictionary) else None

    def set_mh(self, mh: COSDictionary | None) -> None:
        if mh is None:
            self._dict.remove_item(_MH)
            return
        self._dict.set_item(_MH, mh)

    def get_be(self) -> COSDictionary | None:
        v = self._dict.get_dictionary_object(_BE)
        return v if isinstance(v, COSDictionary) else None

    def set_be(self, be: COSDictionary | None) -> None:
        if be is None:
            self._dict.remove_item(_BE)
            return
        self._dict.set_item(_BE, be)

    def get_type(self) -> str | None:
        return self._dict.get_name(_TYPE)

    def get_or_create_mh(self) -> COSDictionary:
        existing = self._dict.get_dictionary_object(_MH)
        if isinstance(existing, COSDictionary):
            return existing
        fresh = COSDictionary()
        self._dict.set_item(_MH, fresh)
        return fresh

    def get_or_create_be(self) -> COSDictionary:
        existing = self._dict.get_dictionary_object(_BE)
        if isinstance(existing, COSDictionary):
            return existing
        fresh = COSDictionary()
        self._dict.set_item(_BE, fresh)
        return fresh

    def __repr__(self) -> str:
        return f"{type(self).__name__}(S={self.get_subtype()!r}, N={self.get_n()!r})"


__all__ = ["PDRendition"]
