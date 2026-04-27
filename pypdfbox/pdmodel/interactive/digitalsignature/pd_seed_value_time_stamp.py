from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSInteger, COSName

_FF: COSName = COSName.get_pdf_name("Ff")
_URL: COSName = COSName.get_pdf_name("URL")

# /Ff bit 1 — URL required (PDF 32000-1 §12.7.4.5, Table 235).
_FLAG_URL = 1 << 0


class PDSeedValueTimeStamp:
    """``/TimeStamp`` sub-dictionary of a seed value (``/Type /SV``) entry.

    Mirrors PDFBox ``PDSeedValueTimeStamp`` (PDF 32000-1 §12.7.4.5,
    Table 235). Provides the URL of a timestamp authority (RFC 3161 server)
    and a single ``/Ff`` required-flag indicating whether the URL must be
    used (bit 1).
    """

    def __init__(self, dict_: COSDictionary | None = None) -> None:
        if dict_ is None:
            self._dict = COSDictionary()
        else:
            self._dict = dict_
        self._dict.set_direct(True)

    def get_cos_object(self) -> COSDictionary:
        """Return the wrapped ``COSDictionary``."""
        return self._dict

    # ---------- /URL ----------

    def get_url(self) -> str | None:
        """Return the timestamp authority URL, or ``None`` if absent."""
        return self._dict.get_string(_URL)

    def set_url(self, url: str | None) -> None:
        """Set or remove the timestamp authority URL."""
        if url is None:
            self._dict.remove_item(_URL)
            return
        self._dict.set_string(_URL, url)

    # ---------- /Ff (URL required flag) ----------

    def _is_flag(self, bit: int) -> bool:
        v = self._dict.get_dictionary_object(_FF)
        if isinstance(v, COSInteger):
            return (v.value & bit) != 0
        return False

    def _set_flag(self, bit: int, value: bool) -> None:
        v = self._dict.get_dictionary_object(_FF)
        current = v.value if isinstance(v, COSInteger) else 0
        new = (current | bit) if value else (current & ~bit)
        self._dict.set_int(_FF, new)

    def is_url_required(self) -> bool:
        """Return ``True`` when the URL must be used (``/Ff`` bit 1)."""
        return self._is_flag(_FLAG_URL)

    def set_url_required(self, flag: bool) -> None:
        """Set the URL-required ``/Ff`` bit (bit 1)."""
        self._set_flag(_FLAG_URL, flag)


__all__ = ["PDSeedValueTimeStamp"]
