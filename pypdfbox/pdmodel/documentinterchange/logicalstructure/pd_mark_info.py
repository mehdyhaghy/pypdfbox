from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName

_MARKED: COSName = COSName.get_pdf_name("Marked")
_USER_PROPERTIES: COSName = COSName.get_pdf_name("UserProperties")
_SUSPECTS: COSName = COSName.get_pdf_name("Suspects")


class PDMarkInfo:
    """
    The MarkInfo dictionary referenced by the document catalog
    (``/MarkInfo``). Mirrors PDFBox ``PDMarkInfo``.
    """

    def __init__(self, dictionary: COSDictionary | None = None) -> None:
        self._dictionary: COSDictionary = (
            dictionary if dictionary is not None else COSDictionary()
        )

    def get_cos_object(self) -> COSDictionary:
        return self._dictionary

    def is_marked(self) -> bool:
        return self._dictionary.get_boolean(_MARKED, False)

    def set_marked(self, value: bool) -> None:
        self._dictionary.set_boolean(_MARKED, value)

    def is_user_properties(self) -> bool:
        return self._dictionary.get_boolean(_USER_PROPERTIES, False)

    def uses_user_properties(self) -> bool:
        # Upstream-named accessor (PDFBox: usesUserProperties()).
        return self.is_user_properties()

    def set_user_properties(self, value: bool) -> None:
        self._dictionary.set_boolean(_USER_PROPERTIES, value)

    def is_suspects(self) -> bool:
        return self._dictionary.get_boolean(_SUSPECTS, False)

    def is_suspect(self) -> bool:
        # Upstream-named accessor (PDFBox: isSuspect()); reads the same
        # ``/Suspects`` entry per PDF 32000-1 Table 321.
        return self.is_suspects()

    def set_suspects(self, value: bool) -> None:
        self._dictionary.set_boolean(_SUSPECTS, value)

    def set_suspect(self, value: bool) -> None:
        # Upstream-named mutator (PDFBox: setSuspect()). Upstream's
        # implementation always writes ``false`` regardless of the argument
        # (a longstanding bug); we write the actual value.
        self.set_suspects(value)


__all__ = ["PDMarkInfo"]
