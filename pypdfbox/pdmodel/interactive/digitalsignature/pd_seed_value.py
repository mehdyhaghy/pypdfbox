from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName

from .pd_seed_value_certificate import PDSeedValueCertificate
from .pd_seed_value_mdp import PDSeedValueMDP

_TYPE: COSName = COSName.TYPE  # type: ignore[attr-defined]
_SV: COSName = COSName.get_pdf_name("SV")
_FILTER: COSName = COSName.get_pdf_name("Filter")
_SUB_FILTER: COSName = COSName.get_pdf_name("SubFilter")
_DIGEST_METHOD: COSName = COSName.get_pdf_name("DigestMethod")
_V: COSName = COSName.get_pdf_name("V")
_CERT: COSName = COSName.get_pdf_name("Cert")
_REASONS: COSName = COSName.get_pdf_name("Reasons")
_MDP: COSName = COSName.get_pdf_name("MDP")
_TIME_STAMP: COSName = COSName.get_pdf_name("TimeStamp")
_LEGAL_ATTESTATION: COSName = COSName.get_pdf_name("LegalAttestation")
_ADD_REV_INFO: COSName = COSName.get_pdf_name("AddRevInfo")
_FF: COSName = COSName.get_pdf_name("Ff")

# /Ff required-flag bit positions (PDF 32000-1 Table 234).
_FLAG_FILTER = 1 << 0  # bit 1
_FLAG_SUB_FILTER = 1 << 1  # bit 2
_FLAG_V = 1 << 2  # bit 3
_FLAG_REASON = 1 << 3  # bit 4
_FLAG_LEGAL_ATTESTATION = 1 << 4  # bit 5
_FLAG_ADD_REV_INFO = 1 << 5  # bit 6
_FLAG_DIGEST_METHOD = 1 << 6  # bit 7


class PDSeedValue:
    """Seed value dictionary (``/Type /SV``). Mirrors PDFBox ``PDSeedValue``
    (PDF 32000-1 §12.7.4.5, Table 234).

    Typed wrappers exist for ``/MDP`` (:class:`PDSeedValueMDP`) and ``/Cert``
    (:class:`PDSeedValueCertificate`). ``/TimeStamp`` still returns the raw
    ``COSDictionary`` until a typed wrapper is ported.
    """

    TYPE = "SV"

    def __init__(self, dictionary: COSDictionary | None = None) -> None:
        if dictionary is None:
            self._dict = COSDictionary()
            self._dict.set_item(_TYPE, _SV)
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

    # ---------- /SubFilter (array of names) ----------

    def get_sub_filter(self) -> list[str] | None:
        v = self._dict.get_dictionary_object(_SUB_FILTER)
        if not isinstance(v, COSArray):
            return None
        names = v.to_cos_name_string_list()
        if any(n is None for n in names):
            return None
        return [str(n) for n in names]  # type: ignore[arg-type]

    def set_sub_filter(self, names: list[str] | None) -> None:
        if names is None:
            self._dict.remove_item(_SUB_FILTER)
            return
        self._dict.set_item(_SUB_FILTER, COSArray.of_cos_names(names))

    # ---------- /V version ----------

    def get_v(self) -> int | None:
        v = self._dict.get_dictionary_object(_V)
        if isinstance(v, COSInteger):
            return v.value
        return None

    def set_v(self, v: int | None) -> None:
        if v is None:
            self._dict.remove_item(_V)
            return
        self._dict.set_int(_V, v)

    # ---------- /Reasons (array of text strings) ----------

    def get_reasons(self) -> list[str] | None:
        v = self._dict.get_dictionary_object(_REASONS)
        if not isinstance(v, COSArray):
            return None
        out = v.to_cos_string_string_list()
        if any(s is None for s in out):
            return None
        return [str(s) for s in out]  # type: ignore[arg-type]

    def set_reasons(self, reasons: list[str] | None) -> None:
        if reasons is None:
            self._dict.remove_item(_REASONS)
            return
        self._dict.set_item(_REASONS, COSArray.of_cos_strings(reasons))

    # ---------- /MDP (typed wrapper) ----------

    def get_mdp(self) -> PDSeedValueMDP | None:
        """Return the ``/MDP`` sub-dictionary as a :class:`PDSeedValueMDP`,
        or ``None`` if absent."""
        v = self._dict.get_dictionary_object(_MDP)
        if isinstance(v, COSDictionary):
            return PDSeedValueMDP(v)
        return None

    def set_mdp(self, mdp: PDSeedValueMDP | COSDictionary | None) -> None:
        """Set or remove the ``/MDP`` sub-dictionary. Accepts either a
        :class:`PDSeedValueMDP` (preferred) or a raw ``COSDictionary``."""
        if mdp is None:
            self._dict.remove_item(_MDP)
            return
        if isinstance(mdp, PDSeedValueMDP):
            self._dict.set_item(_MDP, mdp.get_cos_object())
        else:
            self._dict.set_item(_MDP, mdp)

    # PDFBox upstream has a typo'd ``setMPD``; we expose the corrected name
    # as ``set_mdp`` (above) and provide ``set_mpd`` for parity.
    def set_mpd(self, mdp: PDSeedValueMDP | COSDictionary | None) -> None:
        self.set_mdp(mdp)

    # ---------- /TimeStamp raw ----------

    def get_time_stamp(self) -> COSDictionary | None:
        v = self._dict.get_dictionary_object(_TIME_STAMP)
        if isinstance(v, COSDictionary):
            return v
        return None

    def set_time_stamp(self, time_stamp: COSDictionary | None) -> None:
        if time_stamp is None:
            self._dict.remove_item(_TIME_STAMP)
            return
        self._dict.set_item(_TIME_STAMP, time_stamp)

    # ---------- /DigestMethod (array of names) ----------

    def get_digest_method(self) -> list[str]:
        v = self._dict.get_dictionary_object(_DIGEST_METHOD)
        if not isinstance(v, COSArray):
            return []
        names = v.to_cos_name_string_list()
        return [str(n) for n in names if n is not None]

    def set_digest_method(self, names: list[str] | None) -> None:
        if names is None:
            self._dict.remove_item(_DIGEST_METHOD)
            return
        self._dict.set_item(_DIGEST_METHOD, COSArray.of_cos_names(names))

    # ---------- /LegalAttestation (array of text strings) ----------

    def get_legal_attestation(self) -> list[str]:
        v = self._dict.get_dictionary_object(_LEGAL_ATTESTATION)
        if not isinstance(v, COSArray):
            return []
        out = v.to_cos_string_string_list()
        return [str(s) for s in out if s is not None]

    def set_legal_attestation(self, values: list[str] | None) -> None:
        if values is None:
            self._dict.remove_item(_LEGAL_ATTESTATION)
            return
        self._dict.set_item(_LEGAL_ATTESTATION, COSArray.of_cos_strings(values))

    # ---------- /Cert (typed wrapper) ----------

    def get_seed_value_certificate(self) -> PDSeedValueCertificate | None:
        """Return the ``/Cert`` sub-dictionary as a
        :class:`PDSeedValueCertificate`, or ``None`` if absent.

        Mirrors upstream ``PDSeedValue.getSeedValueCertificate``.
        """
        v = self._dict.get_dictionary_object(_CERT)
        if isinstance(v, COSDictionary):
            return PDSeedValueCertificate(v)
        return None

    def set_seed_value_certificate(
        self, cert: PDSeedValueCertificate | COSDictionary | None
    ) -> None:
        """Set or remove the ``/Cert`` sub-dictionary. Accepts either a
        :class:`PDSeedValueCertificate` (preferred) or a raw ``COSDictionary``.
        """
        if cert is None:
            self._dict.remove_item(_CERT)
            return
        if isinstance(cert, PDSeedValueCertificate):
            self._dict.set_item(_CERT, cert.get_cos_object())
        else:
            self._dict.set_item(_CERT, cert)

    # PRD-required short aliases.
    def get_certificate(self) -> PDSeedValueCertificate | None:
        """Alias for :meth:`get_seed_value_certificate`."""
        return self.get_seed_value_certificate()

    def set_certificate(
        self, cert: PDSeedValueCertificate | COSDictionary | None
    ) -> None:
        """Alias for :meth:`set_seed_value_certificate`."""
        self.set_seed_value_certificate(cert)

    # ---------- /Ff required-flag helpers ----------

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

    def is_filter_required(self) -> bool:
        return self._is_flag(_FLAG_FILTER)

    def set_filter_required(self, b: bool) -> None:
        self._set_flag(_FLAG_FILTER, b)

    def is_sub_filter_required(self) -> bool:
        return self._is_flag(_FLAG_SUB_FILTER)

    def set_sub_filter_required(self, b: bool) -> None:
        self._set_flag(_FLAG_SUB_FILTER, b)

    def is_reason_required(self) -> bool:
        return self._is_flag(_FLAG_REASON)

    def set_reason_required(self, b: bool) -> None:
        self._set_flag(_FLAG_REASON, b)

    def is_legal_attestation_required(self) -> bool:
        return self._is_flag(_FLAG_LEGAL_ATTESTATION)

    def set_legal_attestation_required(self, b: bool) -> None:
        self._set_flag(_FLAG_LEGAL_ATTESTATION, b)

    def is_add_rev_info_required(self) -> bool:
        return self._is_flag(_FLAG_ADD_REV_INFO)

    def set_add_rev_info_required(self, b: bool) -> None:
        self._set_flag(_FLAG_ADD_REV_INFO, b)

    def is_digest_method_required(self) -> bool:
        return self._is_flag(_FLAG_DIGEST_METHOD)

    def set_digest_method_required(self, b: bool) -> None:
        self._set_flag(_FLAG_DIGEST_METHOD, b)


__all__ = ["PDSeedValue"]
