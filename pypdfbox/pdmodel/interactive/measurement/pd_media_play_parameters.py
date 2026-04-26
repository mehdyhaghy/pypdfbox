from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName

_MH: COSName = COSName.get_pdf_name("MH")
_BE: COSName = COSName.get_pdf_name("BE")


class PDMediaPlayParameters:
    """``/MP`` (Media Play Parameters) dictionary.

    Mirrors PDFBox ``PDMediaPlayParameters`` — lite surface (must-honor /
    best-effort sub-dictionaries exposed as raw COS for now)."""

    def __init__(self, dictionary: COSDictionary | None = None) -> None:
        self._dict = dictionary if dictionary is not None else COSDictionary()

    def get_cos_object(self) -> COSDictionary:
        return self._dict

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


__all__ = ["PDMediaPlayParameters"]
