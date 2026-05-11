"""Port of ``CreateSignatureBase`` (upstream 1-179).

Base class for the example signers. Loads a PKCS#12 keystore and exposes
``sign(content) -> bytes`` returning a detached PKCS#7 / CMS SignedData
blob suitable for embedding in a PDF signature dictionary.

Library-first: ``cryptography.hazmat.primitives.serialization.pkcs12`` for
keystore loading, ``cryptography.hazmat.primitives.serialization.pkcs7``
for detached PKCS#7 signing.
"""

from __future__ import annotations

from collections.abc import Sequence
from io import BytesIO
from typing import IO

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.serialization import pkcs7, pkcs12

from pypdfbox.examples.signature.sig_utils import SigUtils
from pypdfbox.examples.signature.validation_time_stamp import ValidationTimeStamp
from pypdfbox.pdmodel.interactive.digitalsignature.signature_interface import (
    SignatureInterface,
)


class CreateSignatureBase(SignatureInterface):
    """Detached PKCS#7 signer reading credentials from a PKCS#12 keystore."""

    def __init__(self, keystore_bytes: bytes, pin: str | bytes | None) -> None:
        password: bytes | None
        if pin is None:
            password = None
        elif isinstance(pin, str):
            password = pin.encode("utf-8")
        else:
            password = bytes(pin)

        private_key, cert, additional = pkcs12.load_key_and_certificates(
            keystore_bytes, password
        )
        if cert is None or private_key is None:
            raise OSError("Could not find certificate")

        # validity window — mirrors upstream X509Certificate.checkValidity()
        import datetime as _dt

        now = _dt.datetime.now(_dt.UTC)
        not_before = getattr(cert, "not_valid_before_utc", None) or cert.not_valid_before
        not_after = getattr(cert, "not_valid_after_utc", None) or cert.not_valid_after
        if not_before > now or not_after < now:
            raise OSError("Certificate is not currently valid")

        SigUtils.check_certificate_usage(cert)

        self._private_key = private_key
        self._certificate_chain: list[x509.Certificate] = [cert] + list(additional or [])
        self._tsa_url: str | None = None
        self._external_signing: bool = False

    # ----- properties --------------------------------------------------
    def set_private_key(self, private_key) -> None:  # noqa: ANN001
        self._private_key = private_key

    def set_certificate_chain(self, chain: Sequence[x509.Certificate]) -> None:
        self._certificate_chain = list(chain)

    def get_certificate_chain(self) -> list[x509.Certificate]:
        return list(self._certificate_chain)

    def set_tsa_url(self, tsa_url: str | None) -> None:
        self._tsa_url = tsa_url

    def set_external_signing(self, external: bool) -> None:
        self._external_signing = external

    def is_external_signing(self) -> bool:
        return self._external_signing

    # ----- main API ----------------------------------------------------
    def sign(self, content: IO[bytes]) -> bytes:
        """Return a detached PKCS#7 SignedData blob for ``content``."""
        data = content.read() if hasattr(content, "read") else bytes(content)
        chain_tail = self._certificate_chain[1:] if len(self._certificate_chain) > 1 else []
        builder = (
            pkcs7.PKCS7SignatureBuilder()
            .set_data(data)
            .add_signer(
                self._certificate_chain[0],
                self._private_key,
                hashes.SHA256(),
            )
        )
        for extra in chain_tail:
            builder = builder.add_certificate(extra)
        signed_data = builder.sign(
            serialization.Encoding.DER,
            [pkcs7.PKCS7Options.DetachedSignature],
        )
        if self._tsa_url:
            validation = ValidationTimeStamp(self._tsa_url)
            signed_data = validation.add_signed_time_stamp(signed_data)
        return signed_data

    # Convenience helpers ----------------------------------------------
    def sign_stream(self, payload: bytes) -> bytes:
        return self.sign(BytesIO(payload))
