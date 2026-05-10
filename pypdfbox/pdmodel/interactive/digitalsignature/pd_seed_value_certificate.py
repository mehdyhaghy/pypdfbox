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

    # /URLType standard values (PDF 32000-1 §12.7.4.5, Table 235).
    # ``Browser`` — URL points to enrollment content displayed by a browser.
    # The ``/Ff`` URL bit is *ignored* for this usage (per spec).
    # ``ASSP`` — Adobe Server Signing Protocol; URL points to a server-side
    # signing service. When the URL bit is set, signing must use that server.
    URL_TYPE_BROWSER = "Browser"
    URL_TYPE_ASSP = "ASSP"

    # /KeyUsage character index meanings (PDF 32000-1 §12.7.4.5, Table 235).
    # Each /KeyUsage string is exactly nine characters; the character at index
    # N constrains the X.509v3 KeyUsage bit listed below. A value of '0' means
    # the bit must be clear, '1' means it must be set, 'X' means don't care.
    KEY_USAGE_LENGTH = 9
    KEY_USAGE_INDEX_DIGITAL_SIGNATURE = 0
    KEY_USAGE_INDEX_NON_REPUDIATION = 1
    KEY_USAGE_INDEX_KEY_ENCIPHERMENT = 2
    KEY_USAGE_INDEX_DATA_ENCIPHERMENT = 3
    KEY_USAGE_INDEX_KEY_AGREEMENT = 4
    KEY_USAGE_INDEX_KEY_CERT_SIGN = 5
    KEY_USAGE_INDEX_CRL_SIGN = 6
    KEY_USAGE_INDEX_ENCIPHER_ONLY = 7
    KEY_USAGE_INDEX_DECIPHER_ONLY = 8
    KEY_USAGE_ALLOWED_CHARS = frozenset("01X")

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
        for key_usage_extension in key_usage_extensions:
            self.validate_key_usage_string(key_usage_extension)
        self._dict.set_item(_KEY_USAGE, COSArray.of_cos_strings(key_usage_extensions))

    def add_key_usage(self, key_usage_extension: str) -> None:
        self.validate_key_usage_string(key_usage_extension)
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

    # ---------- /URLType predicates and default handling ----------

    def get_url_type_or_default(self) -> str:
        """Return ``/URLType``, falling back to ``"Browser"`` when absent.

        Mirrors the spec note (PDF 32000-1 §12.7.4.5, Table 235) that "if
        urlType is not set the default is Browser for URL". Use this when
        consuming the URL — :meth:`get_url_type` exposes the raw stored value
        (``None`` when absent) for round-trip / serialisation work.
        """
        existing = self.get_url_type()
        return existing if existing is not None else self.URL_TYPE_BROWSER

    def is_url_type_browser(self) -> bool:
        """Return ``True`` when ``/URLType`` is ``"Browser"`` *or absent*.

        Per the spec the default ``/URLType`` is ``Browser`` when the entry
        is not set, so the predicate matches either case to give callers a
        single test that reflects the *effective* URL type.
        """
        return self.get_url_type_or_default() == self.URL_TYPE_BROWSER

    def is_url_type_assp(self) -> bool:
        """Return ``True`` when ``/URLType`` is ``"ASSP"`` (server-side
        signing service). Strict equality — an absent entry returns
        ``False`` regardless of the spec's ``Browser`` default.
        """
        return self.get_url_type() == self.URL_TYPE_ASSP

    # ---------- /KeyUsage parsing helpers ----------

    @classmethod
    def validate_key_usage_string(cls, key_usage_extension: str) -> None:
        """Raise :class:`ValueError` when ``key_usage_extension`` is not a
        well-formed KeyUsage string.

        Mirrors the validation upstream performs inside ``addKeyUsage`` but
        also enforces the spec-mandated length (exactly 9 characters).
        Allowed characters are ``0``, ``1``, ``X``.
        """
        if len(key_usage_extension) != cls.KEY_USAGE_LENGTH:
            raise ValueError(
                f"KeyUsage extension must be exactly {cls.KEY_USAGE_LENGTH} "
                f"characters, got {len(key_usage_extension)}"
            )
        for ch in key_usage_extension:
            if ch not in cls.KEY_USAGE_ALLOWED_CHARS:
                raise ValueError("characters can only be 0, 1, X")

    @classmethod
    def parse_key_usage(cls, key_usage_extension: str) -> dict[str, str]:
        """Return a ``{name: char}`` map for a 9-char KeyUsage string.

        Convenience helper: turns the positional encoding into an
        addressable map keyed by the X.509 KeyUsage bit names from
        PDF 32000-1 §12.7.4.5, Table 235. Useful when comparing two
        KeyUsage strings or rendering them for diagnostics.

        Raises :class:`ValueError` for malformed inputs (length or charset).
        """
        cls.validate_key_usage_string(key_usage_extension)
        return {
            "digital_signature": key_usage_extension[cls.KEY_USAGE_INDEX_DIGITAL_SIGNATURE],
            "non_repudiation": key_usage_extension[cls.KEY_USAGE_INDEX_NON_REPUDIATION],
            "key_encipherment": key_usage_extension[cls.KEY_USAGE_INDEX_KEY_ENCIPHERMENT],
            "data_encipherment": key_usage_extension[cls.KEY_USAGE_INDEX_DATA_ENCIPHERMENT],
            "key_agreement": key_usage_extension[cls.KEY_USAGE_INDEX_KEY_AGREEMENT],
            "key_cert_sign": key_usage_extension[cls.KEY_USAGE_INDEX_KEY_CERT_SIGN],
            "crl_sign": key_usage_extension[cls.KEY_USAGE_INDEX_CRL_SIGN],
            "encipher_only": key_usage_extension[cls.KEY_USAGE_INDEX_ENCIPHER_ONLY],
            "decipher_only": key_usage_extension[cls.KEY_USAGE_INDEX_DECIPHER_ONLY],
        }

    # ---------- string form ----------

    def __str__(self) -> str:
        """Compact summary of the certificate seed value.

        Java's ``Object.toString()`` is ``ClassName@hashcode``; this lite
        port emits populated subset of ``/Ff`` (as a hex bitmask), and
        counts of the array-valued entries (``/Subject``, ``/SubjectDN``,
        ``/KeyUsage``, ``/Issuer``, ``/OID``), plus ``/URL`` and
        ``/URLType`` when present. An empty dict is summarized as
        ``<empty>``.
        """
        parts: list[str] = []
        if self.has_ff():
            parts.append(f"ff=0x{self.get_ff():x}")
        for label, fetcher in (
            ("subject", self.get_subject),
            ("subject_dn", self.get_subject_dn),
            ("key_usage", self.get_key_usage),
            ("issuer", self.get_issuer),
            ("oid", self.get_oid),
        ):
            v = fetcher()
            if v is not None:
                parts.append(f"{label}={len(v)}")
        url = self.get_url()
        if url:
            parts.append(f"url={url}")
        url_type = self.get_url_type()
        if url_type:
            parts.append(f"url_type={url_type}")
        body = ", ".join(parts) if parts else "<empty>"
        return f"PDSeedValueCertificate({body})"

    def __repr__(self) -> str:
        return self.__str__()

    # ---------- COSArray ↔ list[bytes] conversion (mirror upstream privates) ----------

    @staticmethod
    def convert_list_of_byte_arrays_to_cos_array(byte_arrays: list[bytes]) -> COSArray:
        """Pack a list of byte arrays into a ``COSArray`` of ``COSString``.

        Mirrors upstream private static ``convertListOfByteArraysToCOSArray``.
        """
        return _byte_arrays_to_cos_array(byte_arrays)

    @staticmethod
    def get_list_of_byte_arrays_from_cos_array(array: COSArray) -> list[bytes]:
        """Unpack a ``COSArray`` of ``COSString`` into a list of byte arrays.

        Mirrors upstream private static ``getListOfByteArraysFromCOSArray``.
        Non-string entries are silently skipped (matches upstream's
        ``instanceof COSString`` filter).
        """
        return _byte_arrays_from_cos_array(array)


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
