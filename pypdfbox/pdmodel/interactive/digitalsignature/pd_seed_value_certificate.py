from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSString

_TYPE: COSName = COSName.get_pdf_name("Type")
_SV_CERT: COSName = COSName.get_pdf_name("SVCert")
_FF: COSName = COSName.get_pdf_name("Ff")
_SUBJECT: COSName = COSName.get_pdf_name("Subject")
_SUBJECT_DN: COSName = COSName.get_pdf_name("SubjectDN")
_KEY_USAGE: COSName = COSName.get_pdf_name("KeyUsage")
_ISSUER: COSName = COSName.get_pdf_name("Issuer")
_OID: COSName = COSName.get_pdf_name("OID")
_URL: COSName = COSName.get_pdf_name("URL")
_URL_TYPE: COSName = COSName.get_pdf_name("URLType")


class PDSeedValueCertificate:
    """Certificate seed value sub-dictionary (``/Cert``).

    Constrains certificates acceptable when signing. Mirrors PDFBox
    ``PDSeedValueCertificate`` (PDF 32000-1 §12.7.4.5, Table 235).
    """

    # /Ff flag bits (PDF 32000-1 Table 235).
    FLAG_SUBJECT = 1
    FLAG_ISSUER = 1 << 1
    FLAG_OID = 1 << 2
    FLAG_SUBJECT_DN = 1 << 3
    FLAG_KEY_USAGE = 1 << 5
    FLAG_URL = 1 << 6

    def __init__(self, dict_: COSDictionary | None = None) -> None:
        if dict_ is None:
            self._dict = COSDictionary()
            self._dict.set_item(_TYPE, _SV_CERT)
        else:
            self._dict = dict_
        self._dict.set_direct(True)

    def get_cos_object(self) -> COSDictionary:
        """Return the wrapped ``COSDictionary``."""
        return self._dict

    # ---------- /Ff flag helpers ----------

    def _get_flag(self, bit: int) -> bool:
        from pypdfbox.cos import COSInteger
        v = self._dict.get_dictionary_object(_FF)
        if isinstance(v, COSInteger):
            return (v.value & bit) != 0
        return False

    def _set_flag(self, bit: int, value: bool) -> None:
        from pypdfbox.cos import COSInteger
        v = self._dict.get_dictionary_object(_FF)
        current = v.value if isinstance(v, COSInteger) else 0
        new = (current | bit) if value else (current & ~bit)
        self._dict.set_int(_FF, new)

    def is_subject_required(self) -> bool:
        return self._get_flag(self.FLAG_SUBJECT)

    def set_subject_required(self, flag: bool) -> None:
        self._set_flag(self.FLAG_SUBJECT, flag)

    def is_issuer_required(self) -> bool:
        return self._get_flag(self.FLAG_ISSUER)

    def set_issuer_required(self, flag: bool) -> None:
        self._set_flag(self.FLAG_ISSUER, flag)

    def is_oid_required(self) -> bool:
        return self._get_flag(self.FLAG_OID)

    def set_oid_required(self, flag: bool) -> None:
        self._set_flag(self.FLAG_OID, flag)

    def is_subject_dn_required(self) -> bool:
        return self._get_flag(self.FLAG_SUBJECT_DN)

    def set_subject_dn_required(self, flag: bool) -> None:
        self._set_flag(self.FLAG_SUBJECT_DN, flag)

    def is_key_usage_required(self) -> bool:
        return self._get_flag(self.FLAG_KEY_USAGE)

    def set_key_usage_required(self, flag: bool) -> None:
        self._set_flag(self.FLAG_KEY_USAGE, flag)

    def is_url_required(self) -> bool:
        return self._get_flag(self.FLAG_URL)

    def set_url_required(self, flag: bool) -> None:
        self._set_flag(self.FLAG_URL, flag)

    # ---------- /Subject (array of byte arrays = DER-encoded X.509v3) ----------

    def get_subject(self) -> list[bytes] | None:
        v = self._dict.get_dictionary_object(_SUBJECT)
        if isinstance(v, COSArray):
            return _byte_arrays_from_cos_array(v)
        return None

    def set_subject(self, subjects: list[bytes]) -> None:
        self._dict.set_item(_SUBJECT, _byte_arrays_to_cos_array(subjects))

    def add_subject(self, subject: bytes) -> None:
        v = self._dict.get_dictionary_object(_SUBJECT)
        array = v if isinstance(v, COSArray) else COSArray()
        array.add(COSString(subject))
        self._dict.set_item(_SUBJECT, array)

    def remove_subject(self, subject: bytes) -> None:
        v = self._dict.get_dictionary_object(_SUBJECT)
        if isinstance(v, COSArray):
            v.remove(COSString(subject))

    # ---------- /SubjectDN (array of dictionaries) ----------

    def get_subject_dn(self) -> list[dict[str, str]] | None:
        v = self._dict.get_dictionary_object(_SUBJECT_DN)
        if not isinstance(v, COSArray):
            return None
        result: list[dict[str, str]] = []
        for item in v.to_list():
            if isinstance(item, COSDictionary):
                m: dict[str, str] = {}
                for key in item.key_set():
                    s = item.get_string(key)
                    if s is None:
                        s = ""
                    m[key.get_name()] = s
                result.append(m)
        return result

    def set_subject_dn(self, subject_dn: list[dict[str, str]]) -> None:
        array = COSArray()
        for entry in subject_dn:
            d = COSDictionary()
            for key, value in entry.items():
                d.set_item(key, COSString(value))
            array.add(d)
        self._dict.set_item(_SUBJECT_DN, array)

    # ---------- /KeyUsage (array of 9-char strings) ----------

    def get_key_usage(self) -> list[str] | None:
        v = self._dict.get_dictionary_object(_KEY_USAGE)
        if not isinstance(v, COSArray):
            return None
        out: list[str] = []
        for item in v.to_list():
            if isinstance(item, COSString):
                out.append(item.get_string())
        return out

    def set_key_usage(self, key_usage_extensions: list[str]) -> None:
        self._dict.set_item(_KEY_USAGE, COSArray.of_cos_strings(key_usage_extensions))

    def add_key_usage(self, key_usage_extension: str) -> None:
        for ch in key_usage_extension:
            if ch not in "01X":
                raise ValueError("characters can only be 0, 1, X")
        v = self._dict.get_dictionary_object(_KEY_USAGE)
        array = v if isinstance(v, COSArray) else COSArray()
        array.add(COSString(key_usage_extension))
        self._dict.set_item(_KEY_USAGE, array)

    def add_key_usage_chars(
        self,
        digital_signature: str,
        non_repudiation: str,
        key_encipherment: str,
        data_encipherment: str,
        key_agreement: str,
        key_cert_sign: str,
        crl_sign: str,
        encipher_only: str,
        decipher_only: str,
    ) -> None:
        """Build the 9-character key-usage string from individual chars
        and call :meth:`add_key_usage`. Mirrors the upstream ``addKeyUsage``
        overload that takes nine ``char`` parameters.
        """
        joined = "".join(
            (
                digital_signature,
                non_repudiation,
                key_encipherment,
                data_encipherment,
                key_agreement,
                key_cert_sign,
                crl_sign,
                encipher_only,
                decipher_only,
            )
        )
        self.add_key_usage(joined)

    def remove_key_usage(self, key_usage_extension: str) -> None:
        v = self._dict.get_dictionary_object(_KEY_USAGE)
        if isinstance(v, COSArray):
            v.remove(COSString(key_usage_extension))

    # ---------- /Issuer (array of byte arrays = DER-encoded X.509v3) ----------

    def get_issuer(self) -> list[bytes] | None:
        v = self._dict.get_dictionary_object(_ISSUER)
        if isinstance(v, COSArray):
            return _byte_arrays_from_cos_array(v)
        return None

    def set_issuer(self, issuers: list[bytes]) -> None:
        self._dict.set_item(_ISSUER, _byte_arrays_to_cos_array(issuers))

    def add_issuer(self, issuer: bytes) -> None:
        v = self._dict.get_dictionary_object(_ISSUER)
        array = v if isinstance(v, COSArray) else COSArray()
        array.add(COSString(issuer))
        self._dict.set_item(_ISSUER, array)

    def remove_issuer(self, issuer: bytes) -> None:
        v = self._dict.get_dictionary_object(_ISSUER)
        if isinstance(v, COSArray):
            v.remove(COSString(issuer))

    # ---------- /OID (array of byte arrays = OID bytes) ----------

    def get_oid(self) -> list[bytes] | None:
        v = self._dict.get_dictionary_object(_OID)
        if isinstance(v, COSArray):
            return _byte_arrays_from_cos_array(v)
        return None

    def set_oid(self, oid_byte_strings: list[bytes]) -> None:
        self._dict.set_item(_OID, _byte_arrays_to_cos_array(oid_byte_strings))

    def add_oid(self, oid: bytes) -> None:
        v = self._dict.get_dictionary_object(_OID)
        array = v if isinstance(v, COSArray) else COSArray()
        array.add(COSString(oid))
        self._dict.set_item(_OID, array)

    def remove_oid(self, oid: bytes) -> None:
        v = self._dict.get_dictionary_object(_OID)
        if isinstance(v, COSArray):
            v.remove(COSString(oid))

    # ---------- /URL ----------

    def get_url(self) -> str | None:
        return self._dict.get_string(_URL)

    def set_url(self, url: str) -> None:
        self._dict.set_string(_URL, url)

    # ---------- /URLType ----------

    def get_url_type(self) -> str | None:
        # Upstream uses getNameAsString — accepts either a name or string.
        return self._dict.get_string(_URL_TYPE)

    def set_url_type(self, url_type: str) -> None:
        self._dict.set_name(_URL_TYPE, url_type)

    # ---------- /Ff raw accessors ----------
    #
    # Upstream uses ``COSDictionary.getFlag`` / ``setFlag`` to read individual
    # bits. The full integer is occasionally useful for low-level inspection
    # (e.g. round-tripping through a COSDictionary built externally) — these
    # raw accessors expose it without re-deriving via per-bit reads.

    def get_ff(self) -> int:
        """Return the raw ``/Ff`` integer (default ``0`` when absent).

        Mirrors upstream ``COSDictionary.getInt(COSName.FF, 0)``.
        """
        from pypdfbox.cos import COSInteger
        v = self._dict.get_dictionary_object(_FF)
        if isinstance(v, COSInteger):
            return int(v.value)
        return 0

    def set_ff(self, flags: int) -> None:
        """Write the raw ``/Ff`` integer.

        Mirrors upstream ``COSDictionary.setInt(COSName.FF, flags)``. Values
        bitwise-OR'd from the ``FLAG_*`` constants on this class.
        """
        self._dict.set_int(_FF, int(flags))

    # ---------- has_* predicate helpers ----------
    #
    # Predicate-pair siblings of the ``get_*`` accessors above. Cheaper than
    # ``get_*() is not None`` for the array-valued entries (skips list
    # construction) and clearer at call sites. Mirrors the ``has_*`` pattern
    # already established on :class:`PDSeedValue`.

    def has_ff(self) -> bool:
        return self._dict.contains_key(_FF)

    def has_subject(self) -> bool:
        return self._dict.contains_key(_SUBJECT)

    def has_subject_dn(self) -> bool:
        return self._dict.contains_key(_SUBJECT_DN)

    def has_key_usage(self) -> bool:
        return self._dict.contains_key(_KEY_USAGE)

    def has_issuer(self) -> bool:
        return self._dict.contains_key(_ISSUER)

    def has_oid(self) -> bool:
        return self._dict.contains_key(_OID)

    def has_url(self) -> bool:
        return self._dict.contains_key(_URL)

    def has_url_type(self) -> bool:
        return self._dict.contains_key(_URL_TYPE)


def _byte_arrays_from_cos_array(array: COSArray) -> list[bytes]:
    out: list[bytes] = []
    for item in array.to_list():
        if isinstance(item, COSString):
            out.append(item.get_bytes())
    return out


def _byte_arrays_to_cos_array(byte_arrays: list[bytes]) -> COSArray:
    array = COSArray()
    for b in byte_arrays:
        array.add(COSString(b))
    return array


__all__ = ["PDSeedValueCertificate"]
