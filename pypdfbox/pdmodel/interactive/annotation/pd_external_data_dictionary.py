"""``/ExData`` external-data dictionary wrapper.

Mirrors ``org.apache.pdfbox.pdmodel.interactive.annotation.PDExternalDataDictionary``
(PDFBox 3.0, ``pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/
annotation/PDExternalDataDictionary.java``).
"""

from __future__ import annotations

from pypdfbox.cos.cos_dictionary import COSDictionary
from pypdfbox.cos.cos_name import COSName
from pypdfbox.pdmodel.common.cos_objectable import COSObjectable


class PDExternalDataDictionary(COSObjectable):
    """Wraps an ``/ExData`` dictionary entry."""

    def __init__(self, dictionary: COSDictionary | None = None) -> None:
        if dictionary is None:
            self._data_dictionary = COSDictionary()
            self._data_dictionary.set_name(COSName.TYPE, "ExData")
        else:
            self._data_dictionary = dictionary

    def get_cos_object(self) -> COSDictionary:
        return self._data_dictionary

    def get_type(self) -> str:
        return self._data_dictionary.get_name_as_string(COSName.TYPE, "ExData")

    def get_subtype(self) -> str | None:
        return self._data_dictionary.get_name_as_string(COSName.SUBTYPE)

    def set_subtype(self, subtype: str) -> None:
        self._data_dictionary.set_name(COSName.SUBTYPE, subtype)


__all__ = ["PDExternalDataDictionary"]
