from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class SignatureValidationResult:
    """Outcome of :meth:`PDSignature.verify` against a document's bytes.

    Fields capture both the high-level pass/fail (``is_valid``) and the
    structured material a caller might want to inspect (signer certificate
    and convenience accessors, the digest from the signature, the digest we
    computed locally, the signing time when present, and any errors that
    prevented validation).
    """

    is_valid: bool = False
    signer_certificate: Any | None = None
    signer_subject: str | None = None
    signer_serial_number: int | None = None
    signed_digest: bytes | None = None
    computed_digest: bytes | None = None
    signing_time: datetime | None = None
    errors: list[str] = field(default_factory=list)

    # ---------- predicate helpers ----------

    def has_errors(self) -> bool:
        """Return ``True`` when at least one error string was recorded.

        Equivalent to ``bool(result.errors)`` but reads more naturally at
        call sites that are already chaining other ``has_*`` checks. A
        successful verification with :attr:`is_valid` ``True`` may still
        carry warning entries (none of upstream's failure paths set
        ``is_valid=True`` *and* leave errors, but the dataclass shape does
        not enforce that — callers writing their own results may).
        """
        return bool(self.errors)

    def has_signer(self) -> bool:
        """Return ``True`` when a signer certificate was recovered from the
        PKCS#7 blob.

        Distinct from :attr:`is_valid`: a digest mismatch yields
        ``is_valid=False`` *and* a recovered signer cert, while a malformed
        ``/Contents`` blob yields ``is_valid=False`` *without* a cert. Use
        this predicate to disambiguate the two failure modes.
        """
        return self.signer_certificate is not None

    def has_signed_digest(self) -> bool:
        """Return ``True`` when the ``messageDigest`` signed-attribute was
        recovered from the PKCS#7 blob.

        ``signed_digest`` is ``None`` when the PKCS#7 blob is malformed or
        when the OID scan inside :meth:`PDSignature.verify` failed to
        locate ``id-pkcs9-at-messageDigest``. The digest-match check is
        only meaningful when this returns ``True``.
        """
        return self.signed_digest is not None

    def has_computed_digest(self) -> bool:
        """Return ``True`` when the local digest over ``/ByteRange`` was
        computed.

        ``computed_digest`` is ``None`` only when the verify step bailed
        out before hashing (e.g. missing ``/ByteRange`` or ``/Contents``).
        Mirrors the rationale of :meth:`has_signed_digest`.
        """
        return self.computed_digest is not None

    def digest_matches(self) -> bool:
        """Return ``True`` when both digests were recovered *and* are equal.

        Cheap byte-string comparison. Returns ``False`` if either digest is
        absent — callers that need to disambiguate "missing" from "mismatch"
        should consult :meth:`has_signed_digest` and
        :meth:`has_computed_digest` instead.
        """
        if self.signed_digest is None or self.computed_digest is None:
            return False
        return self.signed_digest == self.computed_digest

    # ---------- mutators ----------

    def add_error(self, message: str) -> None:
        """Append ``message`` to :attr:`errors` and force :attr:`is_valid`
        to ``False``.

        Centralises the "record-an-error-and-fail" idiom that
        :meth:`PDSignature.verify` uses on every failure path. Mirrors
        upstream PDFBox's pattern of appending to a result errors list and
        clearing the validity flag together.
        """
        self.errors.append(message)
        self.is_valid = False


__all__ = ["SignatureValidationResult"]
