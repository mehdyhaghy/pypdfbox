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


__all__ = ["SignatureValidationResult"]
