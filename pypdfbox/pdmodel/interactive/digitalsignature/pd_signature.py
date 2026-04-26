from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName, COSString

_TYPE: COSName = COSName.TYPE  # type: ignore[attr-defined]
_SIG: COSName = COSName.get_pdf_name("Sig")
_FILTER: COSName = COSName.get_pdf_name("Filter")
_SUB_FILTER: COSName = COSName.get_pdf_name("SubFilter")
_NAME: COSName = COSName.get_pdf_name("Name")
_LOCATION: COSName = COSName.get_pdf_name("Location")
_REASON: COSName = COSName.get_pdf_name("Reason")
_CONTACT_INFO: COSName = COSName.get_pdf_name("ContactInfo")
_M: COSName = COSName.get_pdf_name("M")
_BYTE_RANGE: COSName = COSName.get_pdf_name("ByteRange")
_CONTENTS: COSName = COSName.get_pdf_name("Contents")


class PDSignature:
    """Signature value dictionary (``/Type /Sig``). Mirrors PDFBox
    ``PDSignature`` lite surface (PDF 32000-1 §12.8.1, Table 252).

    Deferred upstream behavior: structured ``Calendar`` / ``datetime``
    conversion for ``/M`` is not implemented (raw PDF date strings only),
    actual signing/verification (``/Contents`` placeholder population,
    PKCS#7 generation) is out of scope for this lite port.
    """

    TYPE = "Sig"

    def __init__(self, dictionary: COSDictionary | None = None) -> None:
        if dictionary is None:
            self._dict = COSDictionary()
            self._dict.set_item(_TYPE, _SIG)
        else:
            self._dict = dictionary

    def get_cos_object(self) -> COSDictionary:
        return self._dict

    # ---------- /Filter ----------

    def get_filter(self) -> str | None:
        return self._dict.get_name(_FILTER)

    def set_filter(self, name: str | None) -> None:
        if name is None:
            self._dict.remove_item(_FILTER)
            return
        self._dict.set_name(_FILTER, name)

    # ---------- /SubFilter ----------

    def get_sub_filter(self) -> str | None:
        return self._dict.get_name(_SUB_FILTER)

    def set_sub_filter(self, name: str | None) -> None:
        if name is None:
            self._dict.remove_item(_SUB_FILTER)
            return
        self._dict.set_name(_SUB_FILTER, name)

    # ---------- /Name ----------

    def get_name(self) -> str | None:
        return self._dict.get_string(_NAME)

    def set_name(self, name: str | None) -> None:
        if name is None:
            self._dict.remove_item(_NAME)
            return
        self._dict.set_string(_NAME, name)

    # ---------- /Location ----------

    def get_location(self) -> str | None:
        return self._dict.get_string(_LOCATION)

    def set_location(self, location: str | None) -> None:
        if location is None:
            self._dict.remove_item(_LOCATION)
            return
        self._dict.set_string(_LOCATION, location)

    # ---------- /Reason ----------

    def get_reason(self) -> str | None:
        return self._dict.get_string(_REASON)

    def set_reason(self, reason: str | None) -> None:
        if reason is None:
            self._dict.remove_item(_REASON)
            return
        self._dict.set_string(_REASON, reason)

    # ---------- /ContactInfo ----------

    def get_contact_info(self) -> str | None:
        return self._dict.get_string(_CONTACT_INFO)

    def set_contact_info(self, contact_info: str | None) -> None:
        if contact_info is None:
            self._dict.remove_item(_CONTACT_INFO)
            return
        self._dict.set_string(_CONTACT_INFO, contact_info)

    # ---------- /M sign date ----------

    def get_sign_date(self) -> str | None:
        return self._dict.get_string(_M)

    def set_sign_date(self, sign_date: str | None) -> None:
        if sign_date is None:
            self._dict.remove_item(_M)
            return
        self._dict.set_string(_M, sign_date)

    # ---------- /ByteRange ----------

    def get_byte_range(self) -> list[int] | None:
        v = self._dict.get_dictionary_object(_BYTE_RANGE)
        if not isinstance(v, COSArray):
            return None
        ints = v.to_cos_number_integer_list()
        if any(i is None for i in ints):
            return None
        return [int(i) for i in ints]  # type: ignore[arg-type]

    def set_byte_range(self, byte_range: list[int] | None) -> None:
        if byte_range is None:
            self._dict.remove_item(_BYTE_RANGE)
            return
        if len(byte_range) != 4:
            raise ValueError(
                f"ByteRange must have exactly 4 entries, got {len(byte_range)}"
            )
        self._dict.set_item(_BYTE_RANGE, COSArray.of_cos_integers(byte_range))

    # ---------- /Contents ----------

    def get_contents(self) -> bytes | None:
        v = self._dict.get_dictionary_object(_CONTENTS)
        if isinstance(v, COSString):
            return v.get_bytes()
        return None

    def set_contents(self, contents: bytes | None) -> None:
        if contents is None:
            self._dict.remove_item(_CONTENTS)
            return
        s = COSString(contents)
        s.set_force_hex_form(True)
        self._dict.set_item(_CONTENTS, s)


__all__ = ["PDSignature"]
