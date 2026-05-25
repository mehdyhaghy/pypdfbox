"""Wave 1403 branch round-out for ``cert_information_helper``.

Closes ``64->59``: an Authority Information Access description whose access
method is neither OCSP nor caIssuers (or whose location is not a URI) matches
neither branch, so the ``elif ... CA_ISSUERS`` check takes its False arc and
the loop advances to the next description.
"""

from __future__ import annotations

import datetime as _dt

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from pypdfbox.examples.signature.validation.cert_information_helper import (
    CertInformationHelper,
)
from pypdfbox.examples.signature.validation.cert_signature_information import (
    CertSignatureInformation,
)

# A non-standard AIA access method OID (not OCSP, not caIssuers).
_OTHER_ACCESS_METHOD = x509.ObjectIdentifier("1.3.6.1.5.5.7.48.3")


def _cert_with_unknown_aia_method() -> x509.Certificate:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "AIA Test")])
    now = _dt.datetime.now(_dt.UTC)
    return (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - _dt.timedelta(days=1))
        .not_valid_after(now + _dt.timedelta(days=365))
        .add_extension(
            x509.AuthorityInformationAccess(
                [
                    x509.AccessDescription(
                        access_method=_OTHER_ACCESS_METHOD,
                        access_location=x509.UniformResourceIdentifier(
                            "http://other.test.invalid/endpoint"
                        ),
                    )
                ]
            ),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )


def test_authority_info_skips_unknown_access_method() -> None:
    cert = _cert_with_unknown_aia_method()
    info = CertSignatureInformation()
    CertInformationHelper.get_authority_info_extension_value(cert, info)
    # Neither OCSP nor caIssuers matched → 64->59 → no URLs recorded.
    assert info.get_ocsp_url() is None
    assert info.get_issuer_url() is None
