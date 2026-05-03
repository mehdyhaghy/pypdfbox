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
        """Return ``True`` when the URL must be used (``/Ff`` bit 1).

        Note: upstream PDFBox names this ``isTimestampRequired``; both names
        are exposed for compatibility — see :meth:`is_timestamp_required`.
        """
        return self._is_flag(_FLAG_URL)

    def set_url_required(self, flag: bool) -> None:
        """Set the URL-required ``/Ff`` bit (bit 1).

        See :meth:`set_timestamp_required` for the upstream-named alias.
        """
        self._set_flag(_FLAG_URL, flag)

    def is_timestamp_required(self) -> bool:
        """Return ``True`` when the timestamp is required, mirroring
        upstream ``isTimestampRequired()``. Internally checks ``/Ff != 0``
        (any nonzero value, per upstream)."""
        v = self._dict.get_dictionary_object(_FF)
        if isinstance(v, COSInteger):
            return v.value != 0
        return False

    def set_timestamp_required(self, flag: bool) -> None:
        """Set the timestamp-required ``/Ff`` integer to ``1`` (true) or
        ``0`` (false). Mirrors upstream ``setTimestampRequired(boolean)``."""
        self._dict.set_int(_FF, 1 if flag else 0)

    # ---------- predicates ----------

    def has_url(self) -> bool:
        """Return ``True`` when a ``/URL`` entry is present.

        Distinct from :meth:`get_url` returning ``None`` — both empty-string
        and absent URLs surface as ``None`` from :meth:`get_url`, but only an
        absent ``/URL`` returns ``False`` here.
        """
        return self._dict.contains_key(_URL)

    def clear_ff(self) -> None:
        """Remove the ``/Ff`` entry entirely.

        After this call both :meth:`is_url_required` and
        :meth:`is_timestamp_required` return ``False``. Distinct from
        ``set_url_required(False)`` which writes ``0`` instead of removing
        the key.
        """
        self._dict.remove_item(_FF)

    # ---------- string form ----------

    def __str__(self) -> str:
        """Compact summary of the timestamp seed value.

        Java's ``Object.toString()`` is ``ClassName@hashcode``. This lite
        port emits the URL (when set) and a ``required=True`` marker only
        when the timestamp is required. An empty dict is summarized as
        ``<empty>``.
        """
        parts: list[str] = []
        url = self.get_url()
        if url:
            parts.append(f"url={url}")
        if self.is_timestamp_required():
            parts.append("required=True")
        body = ", ".join(parts) if parts else "<empty>"
        return f"PDSeedValueTimeStamp({body})"

    def __repr__(self) -> str:
        return self.__str__()


__all__ = ["PDSeedValueTimeStamp"]
