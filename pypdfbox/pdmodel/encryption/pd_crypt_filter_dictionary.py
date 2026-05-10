"""``/CF`` crypt-filter sub-dictionary wrapper.

Mirrors ``org.apache.pdfbox.pdmodel.encryption.PDCryptFilterDictionary``. A
crypt filter dictionary describes how a particular encryption algorithm
(``/CFM`` — V2 / AESV2 / AESV3 / None) is applied to streams or strings, and
what key length to use. The /Encrypt dictionary references one or more crypt
filters by name through its /CF entry, and selects a default for streams via
/StmF and for strings via /StrF (PDF 32000-1 §7.6.5).
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSBoolean, COSDictionary, COSName, COSNumber

_TYPE: COSName = COSName.get_pdf_name("Type")
_CRYPT_FILTER: COSName = COSName.get_pdf_name("CryptFilter")
_CFM: COSName = COSName.get_pdf_name("CFM")
_LENGTH: COSName = COSName.get_pdf_name("Length")
_RECIPIENTS: COSName = COSName.get_pdf_name("Recipients")
_ENCRYPT_METADATA: COSName = COSName.get_pdf_name("EncryptMetadata")


class PDCryptFilterDictionary:
    """Wraps an entry of the ``/Encrypt /CF`` sub-dictionary.

    Field semantics follow PDF 32000-1 §7.6.5 Table 25:

    * ``/CFM`` — the crypt-filter method name. One of ``None`` / ``V2`` /
      ``AESV2`` / ``AESV3``. Determines whether RC4 or AES (and which key
      size) is used for objects assigned to this filter.
    * ``/Length`` — key length in **bytes** (note: at the /CF level upstream
      PDFBox uses bytes, not bits; defaults to 5 = 40-bit RC4).
    * ``/Recipients`` — required for public-key crypt filters; an array of
      PKCS#7 envelopes.
    * ``/EncryptMetadata`` — whether the document metadata stream should be
      encrypted by this filter. Defaults to ``True``.
    """

    # ``/CFM`` values per PDF 32000-1 §7.6.5 Table 25.
    CFM_NONE: str = "None"
    CFM_V2: str = "V2"
    CFM_AESV2: str = "AESV2"
    CFM_AESV3: str = "AESV3"

    def __init__(self, dictionary: COSDictionary | None = None) -> None:
        if dictionary is None:
            self._dict: COSDictionary = COSDictionary()
            # Fresh crypt-filter dictionaries are tagged ``/Type /CryptFilter``
            # per the spec (it's optional but PDFBox always writes it).
            self._dict.set_item(_TYPE, _CRYPT_FILTER)
        else:
            self._dict = dictionary

    def get_cos_object(self) -> COSDictionary:
        return self._dict

    def get_cos_dictionary(self) -> COSDictionary:
        """Return the wrapped crypt-filter dictionary.

        Mirrors upstream ``getCOSDictionary()`` for this dictionary-only
        wrapper while preserving the existing ``get_cos_object`` spelling.
        """
        return self._dict

    # ---------- /CFM ----------

    def get_crypt_filter_method(self) -> COSName | None:
        """Return the raw ``/CFM`` COS name.

        Mirrors PDFBox ``getCryptFilterMethod()``; callers that need the
        string value can use :meth:`get_cfm`.
        """
        v = self._dict.get_dictionary_object(_CFM)
        if isinstance(v, COSName):
            return v
        return None

    def set_crypt_filter_method(self, cfm: COSName | str | None) -> None:
        """Set the raw ``/CFM`` COS name.

        ``str`` is accepted as the local Python convenience; ``None`` clears
        the entry, matching the existing name-setter semantics.
        """
        if cfm is None:
            self._dict.remove_item(_CFM)
        elif isinstance(cfm, COSName):
            self._dict.set_item(_CFM, cfm)
        elif isinstance(cfm, str):
            self._dict.set_item(_CFM, COSName.get_pdf_name(cfm))
        else:
            msg = f"cfm must be COSName, str, or None, got {type(cfm).__name__}"
            raise TypeError(msg)

    def get_cfm(self) -> str | None:
        cfm = self.get_crypt_filter_method()
        if cfm is None:
            return None
        return cfm.name

    def set_cfm(self, name: str | None) -> None:
        self.set_crypt_filter_method(name)

    def has_cfm(self) -> bool:
        return isinstance(self._dict.get_dictionary_object(_CFM), COSName)

    def clear_cfm(self) -> None:
        self._dict.remove_item(_CFM)

    # ---------- /Length (in bytes) ----------

    def get_length(self) -> int:
        # Default per PDF 32000-1 §7.6.5 Table 25: 5 bytes (40 bit RC4).
        return self._dict.get_int(_LENGTH, 5)

    def set_length(self, length: int) -> None:
        self._dict.set_int(_LENGTH, length)

    def has_length(self) -> bool:
        return isinstance(self._dict.get_dictionary_object(_LENGTH), COSNumber)

    def clear_length(self) -> None:
        self._dict.remove_item(_LENGTH)

    # ---------- /Recipients (public-key crypt filters) ----------

    def get_recipients(self) -> COSArray | None:
        v = self._dict.get_dictionary_object(_RECIPIENTS)
        if isinstance(v, COSArray):
            return v
        return None

    def set_recipients(self, recipients: COSArray) -> None:
        self._dict.set_item(_RECIPIENTS, recipients)

    def has_recipients(self) -> bool:
        return isinstance(self._dict.get_dictionary_object(_RECIPIENTS), COSArray)

    def clear_recipients(self) -> None:
        self._dict.remove_item(_RECIPIENTS)

    # ---------- /EncryptMetadata ----------

    def get_encrypt_metadata(self) -> bool:
        # Default per PDF 32000-1 §7.6.5 Table 25 is true.
        return self._dict.get_boolean(_ENCRYPT_METADATA, True)

    def set_encrypt_metadata(self, encrypt_metadata: bool) -> None:
        self._dict.set_boolean(_ENCRYPT_METADATA, encrypt_metadata)

    def is_encrypt_meta_data(self) -> bool:
        """Snake-case alias matching upstream ``isEncryptMetaData``.

        Upstream camelCase ``EncryptMetaData`` splits as three words —
        Encrypt, Meta, Data — so the strict snake_case rendering is
        ``is_encrypt_meta_data``. The older :meth:`get_encrypt_metadata`
        spelling treats ``Metadata`` as one word; both are kept so
        existing callers keep working while ports reading PDFBox source
        land on the upstream word boundary.
        """
        return self.get_encrypt_metadata()

    def set_encrypt_meta_data(self, encrypt_meta_data: bool) -> None:
        """Snake-case alias matching upstream ``setEncryptMetaData``.

        Companion to :meth:`is_encrypt_meta_data`. See that method's
        docstring for the word-boundary rationale.
        """
        self.set_encrypt_metadata(encrypt_meta_data)

    def has_encrypt_metadata(self) -> bool:
        return isinstance(self._dict.get_dictionary_object(_ENCRYPT_METADATA), COSBoolean)

    def clear_encrypt_metadata(self) -> None:
        self._dict.remove_item(_ENCRYPT_METADATA)


__all__ = ["PDCryptFilterDictionary"]
