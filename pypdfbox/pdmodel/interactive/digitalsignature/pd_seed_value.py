from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName, COSNumber

from .pd_seed_value_certificate import PDSeedValueCertificate
from .pd_seed_value_mdp import PDSeedValueMDP
from .pd_seed_value_time_stamp import PDSeedValueTimeStamp

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

    Typed wrappers exist for ``/MDP`` (:class:`PDSeedValueMDP`), ``/Cert``
    (:class:`PDSeedValueCertificate`), and ``/TimeStamp``
    (:class:`PDSeedValueTimeStamp`).
    """

    TYPE = "SV"

    # /Ff bit positions (PDF 32000-1 Table 234), exposed for parity.
    FLAG_FILTER = _FLAG_FILTER
    FLAG_SUBFILTER = _FLAG_SUB_FILTER
    FLAG_V = _FLAG_V
    FLAG_REASON = _FLAG_REASON
    FLAG_LEGAL_ATTESTATION = _FLAG_LEGAL_ATTESTATION
    FLAG_ADD_REV_INFO = _FLAG_ADD_REV_INFO
    FLAG_DIGEST_METHOD = _FLAG_DIGEST_METHOD

    # Standard ``/Filter`` signature handler names. Mirrors the
    # ``FILTER_*`` constants on upstream :class:`PDSignature`. PDF 32000-1
    # §12.8.1, Table 252.
    FILTER_ADOBE_PPKLITE = "Adobe.PPKLite"
    FILTER_ENTRUST_PPKEF = "Entrust.PPKEF"
    FILTER_CICI_SIGNIT = "CICI.SignIt"
    FILTER_VERISIGN_PPKVS = "VeriSign.PPKVS"

    # Standard ``/SubFilter`` encodings. Mirrors the ``SUBFILTER_*``
    # constants on upstream :class:`PDSignature`. PDF 32000-1 §12.8.3.
    SUBFILTER_ADBE_X509_RSA_SHA1 = "adbe.x509.rsa_sha1"
    SUBFILTER_ADBE_PKCS7_DETACHED = "adbe.pkcs7.detached"
    SUBFILTER_ETSI_CADES_DETACHED = "ETSI.CAdES.detached"
    SUBFILTER_ADBE_PKCS7_SHA1 = "adbe.pkcs7.sha1"

    # Allowed /DigestMethod values (PDF 32000-1 Table 234). Upstream stores
    # these as the private static ``allowedDigestNames`` list and validates
    # each entry passed to ``setDigestMethod``.
    DIGEST_SHA1 = "SHA1"
    DIGEST_SHA256 = "SHA256"
    DIGEST_SHA384 = "SHA384"
    DIGEST_SHA512 = "SHA512"
    DIGEST_RIPEMD160 = "RIPEMD160"

    ALLOWED_DIGEST_NAMES: tuple[str, ...] = (
        DIGEST_SHA1,
        DIGEST_SHA256,
        DIGEST_SHA384,
        DIGEST_SHA512,
        DIGEST_RIPEMD160,
    )

    def __init__(self, dictionary: COSDictionary | None = None) -> None:
        if dictionary is None:
            self._dict = COSDictionary()
            self._dict.set_item(_TYPE, _SV)
            # Upstream calls dictionary.setDirect(true) in the no-arg ctor.
            self._dict.set_direct(True)
        else:
            self._dict = dictionary

    def get_cos_object(self) -> COSDictionary:
        return self._dict

    # ---------- /Filter ----------

    def get_filter(self) -> str | None:
        """Return the ``/Filter`` value as a string. Mirrors upstream
        ``getNameAsString(COSName.FILTER)`` — handles both ``COSName`` and
        ``COSString`` storage shapes (some producers write a string)."""
        return self._dict.get_string(_FILTER)

    def set_filter(self, name: str | COSName | None) -> None:
        """Set or remove the ``/Filter`` entry. Upstream signature is
        ``setFilter(COSName)``; we accept either ``str`` or ``COSName`` and
        store as a name (``None`` removes the entry)."""
        if name is None:
            self._dict.remove_item(_FILTER)
            return
        if isinstance(name, COSName):
            self._dict.set_item(_FILTER, name)
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
        return [str(n) for n in names]

    def set_sub_filter(self, names: list[str] | None) -> None:
        if names is None:
            self._dict.remove_item(_SUB_FILTER)
            return
        self._dict.set_item(_SUB_FILTER, COSArray.of_cos_names(names))

    # ---------- /V version ----------

    def get_v(self) -> float | None:
        """Return the ``/V`` minimum-required-capability value, or ``None``
        if absent. Mirrors upstream ``getV()`` (returns ``float``)."""
        v = self._dict.get_dictionary_object(_V)
        if isinstance(v, COSNumber):
            return v.float_value()
        return None

    def set_v(self, v: float | None) -> None:
        """Set or remove the ``/V`` entry. Upstream signature is
        ``setV(float)``; we accept ``None`` to remove."""
        if v is None:
            self._dict.remove_item(_V)
            return
        self._dict.set_float(_V, float(v))

    # ---------- /Reasons (array of text strings) ----------

    def get_reasons(self) -> list[str] | None:
        v = self._dict.get_dictionary_object(_REASONS)
        if not isinstance(v, COSArray):
            return None
        out = v.to_cos_string_string_list()
        if any(s is None for s in out):
            return None
        return [str(s) for s in out]

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

    # ---------- /TimeStamp (typed wrapper) ----------

    def get_time_stamp(self) -> PDSeedValueTimeStamp | None:
        """Return the ``/TimeStamp`` sub-dictionary as a
        :class:`PDSeedValueTimeStamp`, or ``None`` if absent.

        Mirrors upstream ``PDSeedValue.getTimeStamp``.
        """
        v = self._dict.get_dictionary_object(_TIME_STAMP)
        if isinstance(v, COSDictionary):
            return PDSeedValueTimeStamp(v)
        return None

    def set_time_stamp(
        self, time_stamp: PDSeedValueTimeStamp | COSDictionary | None
    ) -> None:
        """Set or remove the ``/TimeStamp`` sub-dictionary. Accepts either a
        :class:`PDSeedValueTimeStamp` (preferred) or a raw ``COSDictionary``.
        """
        if time_stamp is None:
            self._dict.remove_item(_TIME_STAMP)
            return
        if isinstance(time_stamp, PDSeedValueTimeStamp):
            self._dict.set_item(_TIME_STAMP, time_stamp.get_cos_object())
        else:
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
        # Integrity check — mirrors upstream's IllegalArgumentException.
        for digest_name in names:
            if digest_name not in self.ALLOWED_DIGEST_NAMES:
                raise ValueError(f"Specified digest {digest_name} isn't allowed.")
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

    def is_v_required(self) -> bool:
        return self._is_flag(_FLAG_V)

    def set_v_required(self, b: bool) -> None:
        self._set_flag(_FLAG_V, b)

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

    # ---------- pypdfbox-only own-dictionary predicates ----------
    #
    # Upstream returns ``null`` / empty list when entries are absent and
    # callers test that. These ``has_*`` helpers are cheaper than
    # ``get_*() is not None`` for sub-dicts (skip wrapper construction)
    # and clearer at call sites. Mirrors the ``has_*`` predicate-pair
    # pattern already established on :class:`PDSignatureField`.

    def has_filter(self) -> bool:
        return self._dict.contains_key(_FILTER)

    def has_sub_filter(self) -> bool:
        return self._dict.contains_key(_SUB_FILTER)

    def has_v(self) -> bool:
        return self._dict.contains_key(_V)

    def has_reasons(self) -> bool:
        return self._dict.contains_key(_REASONS)

    def has_legal_attestation(self) -> bool:
        return self._dict.contains_key(_LEGAL_ATTESTATION)

    def has_digest_method(self) -> bool:
        return self._dict.contains_key(_DIGEST_METHOD)

    def has_mdp(self) -> bool:
        return self._dict.contains_key(_MDP)

    def has_time_stamp(self) -> bool:
        return self._dict.contains_key(_TIME_STAMP)

    def has_seed_value_certificate(self) -> bool:
        return self._dict.contains_key(_CERT)

    def has_certificate(self) -> bool:
        """Alias for :meth:`has_seed_value_certificate` — pairs with
        :meth:`get_certificate` / :meth:`set_certificate`."""
        return self.has_seed_value_certificate()

    # ---------- /SV constraint enforcement (wave 1380) ----------
    #
    # Upstream Apache PDFBox carries the constraint surface on
    # ``PDSeedValue`` but defers the enforcement to the front-end /
    # signing UI ("respect /Ff required flags before producing a
    # signature"). pypdfbox exposes :meth:`validate_signature` so the
    # signing engine can short-circuit a sign attempt when the candidate
    # ``PDSignature`` violates a flagged ``/SV`` constraint. The check is
    # opt-in via ``PDDocument.add_signature(..., enforce_seed_value=True)``
    # — the default off mirrors upstream's "advisory only" stance.

    def check_signature_constraint(self, signature: object) -> list[str]:
        """Return a list of human-readable violations of this seed value
        by ``signature`` (a :class:`PDSignature`).

        Each entry in the returned list is a one-line description of a
        flagged-required ``/SV`` constraint the candidate signature does
        not satisfy. An empty list means the signature respects every
        flagged constraint. Non-flagged constraints are NOT consulted —
        per PDF 32000-1 §12.7.4.5 a constraint is only mandatory when its
        ``/Ff`` bit is set.

        Constraints checked (each only when its ``/Ff`` bit is set):

        * ``/Filter`` — signature handler name must match.
        * ``/SubFilter`` — signature subfilter must be in the allowed set.
        * ``/V`` — signature can carry no version field of its own, so
          this is a no-op; flagged but no candidate value to compare.
          (PDFBox upstream behaves identically — ``/V`` is a *minimum
          producer capability*, not a per-signature attribute.)
        * ``/Reasons`` — when set the signature ``/Reason`` must be in
          the allowed list.
        * ``/LegalAttestation`` — no per-signature counterpart on
          PDSignature; flagged-required is reported as
          "legal attestation required" since the signing engine cannot
          attest on its own.
        * ``/AddRevInfo`` — pypdfbox does not currently emit revocation
          info in the PKCS#7 blob; flagged-required is reported as
          "revocation info required (unsupported)".
        * ``/DigestMethod`` — checked only when the signature provides a
          :meth:`get_digest_method`-style attribute (custom signers
          attach this); plain :class:`PDSignature` has no /DigestMethod
          slot.
        """
        # Lazy import — pd_signature.py imports from this module via the
        # interactive package, so importing it at module top would cycle.
        from .pd_signature import PDSignature  # noqa: I001 — cycle guard

        violations: list[str] = []
        if not isinstance(signature, PDSignature):
            violations.append(
                f"candidate must be a PDSignature, got {type(signature).__name__}"
            )
            return violations

        # /Filter
        if self.is_filter_required():
            required = self.get_filter()
            actual = signature.get_filter()
            if required is not None and actual != required:
                violations.append(
                    f"/Filter must be {required!r} (signature carries {actual!r})"
                )

        # /SubFilter
        if self.is_sub_filter_required():
            allowed = self.get_sub_filter()
            actual = signature.get_sub_filter()
            if allowed is not None and len(allowed) > 0 and actual not in allowed:
                violations.append(
                    f"/SubFilter must be one of {allowed!r} "
                    f"(signature carries {actual!r})"
                )

        # /Reasons
        if self.is_reason_required():
            allowed_reasons = self.get_reasons()
            actual_reason = signature.get_reason()
            if (
                allowed_reasons is not None
                and len(allowed_reasons) > 0
                and actual_reason not in allowed_reasons
            ):
                violations.append(
                    f"/Reason must be one of {allowed_reasons!r} "
                    f"(signature carries {actual_reason!r})"
                )

        # /LegalAttestation — no PDSignature counterpart; flagged-required
        # is a hard violation because the signing engine can't attest.
        if self.is_legal_attestation_required():
            attestations = self.get_legal_attestation()
            if attestations:
                violations.append(
                    f"/LegalAttestation required, must be one of {attestations!r}"
                )
            else:
                violations.append("/LegalAttestation required (no allowed values set)")

        # /AddRevInfo — pypdfbox does not emit revocation info today.
        if self.is_add_rev_info_required():
            violations.append("/AddRevInfo required (revocation info not supported)")

        # /DigestMethod — only consulted when the signer carries a
        # digest-method attribute (none ships on plain PDSignature).
        if self.is_digest_method_required():
            allowed_digests = self.get_digest_method()
            actual_digest = getattr(signature, "_digest_method_hint", None)
            if (
                allowed_digests
                and actual_digest is not None
                and actual_digest not in allowed_digests
            ):
                violations.append(
                    f"/DigestMethod must be one of {allowed_digests!r} "
                    f"(signature carries {actual_digest!r})"
                )

        return violations

    def validate_signature(self, signature: object) -> None:
        """Raise :class:`ValueError` when ``signature`` violates a flagged
        ``/SV`` constraint. No-op when the seed value is satisfied.

        Convenience wrapper around :meth:`check_signature_constraint` that
        prints every violation in one message — the signing engine reports
        all problems at once rather than failing on the first.
        """
        violations = self.check_signature_constraint(signature)
        if not violations:
            return
        raise ValueError(
            "signature violates /SV seed value constraints: " + "; ".join(violations)
        )


__all__ = ["PDSeedValue", "PDSeedValueTimeStamp"]
