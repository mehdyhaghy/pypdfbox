from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSString

from .pd_crypt_filter_dictionary import PDCryptFilterDictionary

# Algorithm version constants — mirror PDFBox ``PDEncryption`` static fields.
VERSION0_UNDOCUMENTED_UNSUPPORTED: int = 0
VERSION1_40_BIT_ALGORITHM: int = 1
VERSION2_VARIABLE_LENGTH_ALGORITHM: int = 2
VERSION3_UNPUBLISHED_ALGORITHM: int = 3
VERSION4_SECURITY_HANDLER: int = 4

DEFAULT_NAME: str = "Standard"
DEFAULT_LENGTH: int = 40
DEFAULT_VERSION: int = VERSION0_UNDOCUMENTED_UNSUPPORTED

_FILTER: COSName = COSName.get_pdf_name("Filter")
_SUB_FILTER: COSName = COSName.get_pdf_name("SubFilter")
_V: COSName = COSName.get_pdf_name("V")
_LENGTH: COSName = COSName.get_pdf_name("Length")
_R: COSName = COSName.get_pdf_name("R")
_O: COSName = COSName.get_pdf_name("O")
_U: COSName = COSName.get_pdf_name("U")
_OE: COSName = COSName.get_pdf_name("OE")
_UE: COSName = COSName.get_pdf_name("UE")
_PERMS: COSName = COSName.get_pdf_name("Perms")
_P: COSName = COSName.get_pdf_name("P")
_ENCRYPT_METADATA: COSName = COSName.get_pdf_name("EncryptMetadata")
_RECIPIENTS: COSName = COSName.get_pdf_name("Recipients")
_CF: COSName = COSName.get_pdf_name("CF")
_STM_F: COSName = COSName.get_pdf_name("StmF")
_STR_F: COSName = COSName.get_pdf_name("StrF")
_EFF: COSName = COSName.get_pdf_name("EFF")
_STD_CF: COSName = COSName.get_pdf_name("StdCF")
_DEFAULT_CRYPT_FILTER: COSName = COSName.get_pdf_name("DefaultCryptFilter")
_IDENTITY: str = "Identity"


def _get_bytes(d: COSDictionary, key: COSName) -> bytes | None:
    v = d.get_dictionary_object(key)
    if isinstance(v, COSString):
        return v.get_bytes()
    return None


def _set_bytes(d: COSDictionary, key: COSName, value: bytes | None) -> None:
    if value is None:
        d.remove_item(key)
        return
    d.set_item(key, COSString(bytes(value)))


class PDEncryption:
    """
    Wraps the trailer's ``/Encrypt`` dictionary. Mirrors the PDFBox
    ``PDEncryption`` API surface (lite slice — security-handler dispatch and
    crypt-filter sub-dictionaries are deferred).
    """

    def __init__(self, dictionary: COSDictionary | None = None) -> None:
        self._dict: COSDictionary = dictionary if dictionary is not None else COSDictionary()

    def get_cos_object(self) -> COSDictionary:
        return self._dict

    # ---------- /Filter ----------

    def get_filter(self) -> str | None:
        return self._dict.get_name(_FILTER)

    def set_filter(self, name: str) -> None:
        self._dict.set_name(_FILTER, name)

    # ---------- /SubFilter ----------

    def get_sub_filter(self) -> str | None:
        return self._dict.get_name(_SUB_FILTER)

    def set_sub_filter(self, name: str) -> None:
        self._dict.set_name(_SUB_FILTER, name)

    # ---------- /V (algorithm) ----------

    def get_v(self) -> int:
        return self._dict.get_int(_V, DEFAULT_VERSION)

    def set_v(self, v: int) -> None:
        self._dict.set_int(_V, v)

    # ---------- /Length (key length in bits) ----------

    def get_length(self) -> int:
        return self._dict.get_int(_LENGTH, DEFAULT_LENGTH)

    def set_length(self, length: int) -> None:
        self._dict.set_int(_LENGTH, length)

    # ---------- /R (security handler revision) ----------

    def get_revision(self) -> int:
        return self._dict.get_int(_R, DEFAULT_VERSION)

    def set_revision(self, r: int) -> None:
        self._dict.set_int(_R, r)

    # ---------- /O — owner password hash ----------

    def get_o(self) -> bytes | None:
        return _get_bytes(self._dict, _O)

    def set_o(self, b: bytes | None) -> None:
        _set_bytes(self._dict, _O, b)

    # ---------- /U — user password hash ----------

    def get_u(self) -> bytes | None:
        return _get_bytes(self._dict, _U)

    def set_u(self, b: bytes | None) -> None:
        _set_bytes(self._dict, _U, b)

    # ---------- /OE — owner encryption key (R6) ----------

    def get_oe(self) -> bytes | None:
        return _get_bytes(self._dict, _OE)

    def set_oe(self, b: bytes | None) -> None:
        _set_bytes(self._dict, _OE, b)

    # ---------- /UE — user encryption key (R6) ----------

    def get_ue(self) -> bytes | None:
        return _get_bytes(self._dict, _UE)

    def set_ue(self, b: bytes | None) -> None:
        _set_bytes(self._dict, _UE, b)

    # ---------- /Perms (R6) ----------

    def get_perms(self) -> bytes | None:
        return _get_bytes(self._dict, _PERMS)

    def set_perms(self, b: bytes | None) -> None:
        _set_bytes(self._dict, _PERMS, b)

    # ---------- /P — permission integer ----------

    def get_p(self) -> int:
        return self._dict.get_int(_P, 0)

    def set_p(self, p: int) -> None:
        self._dict.set_int(_P, p)

    # ---------- /EncryptMetadata ----------

    def is_encrypt_meta_data(self) -> bool:
        # Default per PDF 32000-1 §7.6.3.2 is true.
        return self._dict.get_boolean(_ENCRYPT_METADATA, True)

    def set_encrypt_meta_data(self, b: bool) -> None:
        self._dict.set_boolean(_ENCRYPT_METADATA, b)

    # ---------- /Recipients (public-key handlers) ----------

    def get_recipients(self) -> COSArray | None:
        v = self._dict.get_dictionary_object(_RECIPIENTS)
        if isinstance(v, COSArray):
            return v
        return None

    # ---------- /CF — crypt-filter sub-dictionary ----------

    def get_cf(self) -> COSDictionary | None:
        v = self._dict.get_dictionary_object(_CF)
        if isinstance(v, COSDictionary):
            return v
        return None

    def set_cf(self, cf: COSDictionary) -> None:
        self._dict.set_item(_CF, cf)

    # ---------- /StmF — default stream filter name ----------

    def get_stm_f(self) -> str | None:
        return self._dict.get_name(_STM_F)

    def set_stm_f(self, name: str) -> None:
        self._dict.set_name(_STM_F, name)

    # ---------- /StrF — default string filter name ----------

    def get_str_f(self) -> str | None:
        return self._dict.get_name(_STR_F)

    def set_str_f(self, name: str) -> None:
        self._dict.set_name(_STR_F, name)

    # ---------- /EFF — default embedded-file filter name ----------

    def get_eff(self) -> str | None:
        return self._dict.get_name(_EFF)

    def set_eff(self, name: str) -> None:
        self._dict.set_name(_EFF, name)

    # ---------- /CF dispatch — typed PDCryptFilterDictionary wrappers ----------

    def get_crypt_filter_dictionary(self, name: str) -> PDCryptFilterDictionary | None:
        """Return the named entry of /CF wrapped in a typed dictionary.

        ``name`` is matched case-sensitively against the keys of the /CF
        sub-dictionary. Returns ``None`` when /CF is absent or the named
        filter does not exist. The "Identity" name is reserved by the spec
        (PDF 32000-1 §7.6.5) and never appears in /CF — callers should
        special-case it before calling here.
        """
        cf = self.get_cf()
        if cf is None:
            return None
        entry = cf.get_dictionary_object(COSName.get_pdf_name(name))
        if isinstance(entry, COSDictionary):
            return PDCryptFilterDictionary(entry)
        return None

    def set_crypt_filter_dictionary(
        self, name: str, dictionary: PDCryptFilterDictionary
    ) -> None:
        """Store ``dictionary`` under ``name`` in /CF, creating /CF if absent."""
        cf = self.get_cf()
        if cf is None:
            cf = COSDictionary()
            self.set_cf(cf)
        # Mirror PDFBox PDFBOX-4436 workaround: keep the entry as a direct
        # object so Adobe Reader on Android resolves it correctly.
        cos_obj = dictionary.get_cos_object()
        cos_obj.set_direct(True)
        cf.set_item(COSName.get_pdf_name(name), cos_obj)

    def get_std_crypt_filter_dictionary(self) -> PDCryptFilterDictionary | None:
        """Return /CF/StdCF wrapped in a typed dictionary, or ``None``."""
        return self.get_crypt_filter_dictionary("StdCF")

    def set_std_crypt_filter_dictionary(
        self, dictionary: PDCryptFilterDictionary
    ) -> None:
        """Store ``dictionary`` under /CF/StdCF (creates /CF if absent)."""
        self.set_crypt_filter_dictionary("StdCF", dictionary)

    def get_default_crypt_filter_dictionary(self) -> PDCryptFilterDictionary | None:
        """Return /CF/DefaultCryptFilter — public-key handler convention."""
        return self.get_crypt_filter_dictionary("DefaultCryptFilter")

    def set_default_crypt_filter_dictionary(
        self, dictionary: PDCryptFilterDictionary
    ) -> None:
        """Store ``dictionary`` under /CF/DefaultCryptFilter."""
        self.set_crypt_filter_dictionary("DefaultCryptFilter", dictionary)

    def remove_v45_filters(self) -> None:
        """Strip /CF, /StmF, /StrF, /EFF — used when downgrading to V <= 3."""
        self._dict.remove_item(_CF)
        self._dict.remove_item(_STM_F)
        self._dict.remove_item(_STR_F)
        self._dict.remove_item(_EFF)


__all__ = [
    "DEFAULT_LENGTH",
    "DEFAULT_NAME",
    "DEFAULT_VERSION",
    "PDCryptFilterDictionary",
    "PDEncryption",
    "VERSION0_UNDOCUMENTED_UNSUPPORTED",
    "VERSION1_40_BIT_ALGORITHM",
    "VERSION2_VARIABLE_LENGTH_ALGORITHM",
    "VERSION3_UNPUBLISHED_ALGORITHM",
    "VERSION4_SECURITY_HANDLER",
]
