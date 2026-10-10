"""Full OCSP response verification in :class:`OcspHelper`.

Builds a tiny PKI in-memory (RSA root CA, leaf, delegated responders with
RSA / EC / Ed25519 / Ed448 keys) and signs OCSP responses with
``cryptography``'s ``OCSPResponseBuilder``. No network: ``perform_request``
is driven through a monkeypatched ``_open_url``.
"""

import datetime as _dt
import email.message
import io

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, ed448, ed25519, rsa
from cryptography.x509 import ocsp
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

from pypdfbox.examples.signature.cert import ocsp_helper as ocsp_mod
from pypdfbox.examples.signature.cert.certificate_verifier import (
    CertificateVerificationException,
    CertificateVerifier,
)
from pypdfbox.examples.signature.cert.ocsp_helper import OcspException, OcspHelper
from pypdfbox.examples.signature.cert.revoked_certificate_exception import (
    RevokedCertificateException,
)

URL = "http://ocsp.test.invalid/check"


def _now() -> _dt.datetime:
    return _dt.datetime.now(_dt.UTC)


def _name(cn: str) -> x509.Name:
    return x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)])


def _sign_alg(key):
    if isinstance(key, (ed25519.Ed25519PrivateKey, ed448.Ed448PrivateKey)):
        return None
    return hashes.SHA256()


def _issue(subject_cn, key, issuer_name, issuer_key, *, ca=False, ocsp_signing=False,
           nocheck=False, eku=None):
    builder = (
        x509.CertificateBuilder()
        .subject_name(_name(subject_cn))
        .issuer_name(issuer_name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(_now() - _dt.timedelta(days=1))
        .not_valid_after(_now() + _dt.timedelta(days=30))
        .add_extension(x509.BasicConstraints(ca=ca, path_length=None), critical=True)
    )
    usages = list(eku or [])
    if ocsp_signing:
        usages.append(ExtendedKeyUsageOID.OCSP_SIGNING)
    if usages:
        builder = builder.add_extension(x509.ExtendedKeyUsage(usages), critical=False)
    if nocheck:
        builder = builder.add_extension(x509.OCSPNoCheck(), critical=False)
    return builder.sign(issuer_key, _sign_alg(issuer_key))


@pytest.fixture(scope="module")
def pki():
    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    ca_cert = _issue("Test Root CA", ca_key, _name("Test Root CA"), ca_key, ca=True)
    leaf_key = ec.generate_private_key(ec.SECP256R1())
    leaf = _issue("leaf", leaf_key, ca_cert.subject, ca_key)
    other_leaf = _issue("other leaf", leaf_key, ca_cert.subject, ca_key)
    return {"ca": ca_cert, "ca_key": ca_key, "leaf": leaf, "other_leaf": other_leaf}


def _responder(pki, key, **kwargs):
    return _issue("OCSP Responder", key, pki["ca"].subject, pki["ca_key"], **kwargs)


def _response(
    pki,
    *,
    cert=None,
    responder_cert=None,
    signing_key=None,
    encoding=ocsp.OCSPResponderEncoding.HASH,
    status=ocsp.OCSPCertStatus.GOOD,
    revocation_time=None,
    this_update=None,
    next_update="default",
    nonce=None,
    include_certs=True,
):
    responder_cert = responder_cert or pki["ca"]
    signing_key = signing_key or pki["ca_key"]
    this_update = this_update or _now() - _dt.timedelta(minutes=5)
    if next_update == "default":
        next_update = _now() + _dt.timedelta(hours=1)
    builder = ocsp.OCSPResponseBuilder().add_response(
        cert=cert or pki["leaf"],
        issuer=pki["ca"],
        algorithm=hashes.SHA1(),
        cert_status=status,
        this_update=this_update,
        next_update=next_update,
        revocation_time=revocation_time,
        revocation_reason=None,
    ).responder_id(encoding, responder_cert)
    if include_certs:
        builder = builder.certificates([responder_cert])
    if nonce is not None:
        builder = builder.add_extension(x509.OCSPNonce(nonce), critical=False)
    return builder.sign(signing_key, _sign_alg(signing_key))


def _helper(pki, *, sign_date=None, additional=None):
    return OcspHelper(
        pki["leaf"],
        sign_date,
        pki["ca"],
        additional if additional is not None else [pki["ca"]],
        URL,
    )


# ---------------------------------------------------------------------------
# Good paths
# ---------------------------------------------------------------------------


def test_good_response_signed_by_issuer(pki):
    helper = _helper(pki)
    resp = _response(pki)
    helper.verify_ocsp_response(resp)
    assert helper.get_ocsp_responder_certificate() == pki["ca"]
    assert helper.get_basic_ocsp_resp() is resp


def test_good_response_responder_by_name(pki):
    helper = _helper(pki)
    helper.verify_ocsp_response(_response(pki, encoding=ocsp.OCSPResponderEncoding.NAME))
    assert helper.get_ocsp_responder_certificate() == pki["ca"]


def test_responder_found_in_additional_certs_when_not_in_response(pki):
    helper = _helper(pki)
    helper.verify_ocsp_response(_response(pki, include_certs=False))
    assert helper.get_ocsp_responder_certificate() == pki["ca"]


@pytest.mark.parametrize(
    "make_key",
    [
        lambda: rsa.generate_private_key(public_exponent=65537, key_size=2048),
        lambda: ec.generate_private_key(ec.SECP384R1()),
        ed25519.Ed25519PrivateKey.generate,
        ed448.Ed448PrivateKey.generate,
    ],
    ids=["rsa", "ecdsa", "ed25519", "ed448"],
)
def test_good_response_from_delegated_responder(pki, make_key):
    key = make_key()
    responder = _responder(pki, key, ocsp_signing=True)
    helper = _helper(pki)
    helper.verify_ocsp_response(
        _response(pki, responder_cert=responder, signing_key=key)
    )
    assert helper.get_ocsp_responder_certificate() == responder


def test_matching_nonce_is_accepted_and_skips_freshness(pki):
    helper = _helper(pki)
    nonce = helper.create16_bytes_nonce()
    # Stale response, but a matching nonce proves freshness (upstream).
    resp = _response(
        pki,
        nonce=nonce,
        this_update=_now() - _dt.timedelta(days=3),
        next_update=_now() - _dt.timedelta(days=2),
    )
    assert helper.check_nonce(resp) is True
    helper.verify_ocsp_response(resp)


def test_revoked_after_signing_is_accepted(pki):
    revoked_at = _now() - _dt.timedelta(hours=1)
    helper = _helper(pki, sign_date=revoked_at - _dt.timedelta(days=1))
    helper.verify_ocsp_response(
        _response(pki, status=ocsp.OCSPCertStatus.REVOKED, revocation_time=revoked_at)
    )


def test_revoked_before_signing_raises(pki):
    revoked_at = _now() - _dt.timedelta(hours=1)
    helper = _helper(pki, sign_date=_now())
    with pytest.raises(RevokedCertificateException):
        helper.verify_ocsp_response(
            _response(pki, status=ocsp.OCSPCertStatus.REVOKED, revocation_time=revoked_at)
        )


# ---------------------------------------------------------------------------
# Rejections
# ---------------------------------------------------------------------------


def test_bad_signature_rejected(pki):
    from cryptography.hazmat.primitives import serialization

    good = _response(pki)
    der = good.public_bytes(serialization.Encoding.DER)
    sig = good.signature
    tampered_sig = sig[:-1] + bytes([sig[-1] ^ 0xFF])
    assert der.count(sig) == 1
    resp = ocsp.load_der_ocsp_response(der.replace(sig, tampered_sig))
    helper = _helper(pki)
    with pytest.raises(OcspException, match="OCSP-Signature is not valid"):
        helper.verify_ocsp_response(resp)
    assert helper.get_basic_ocsp_resp() is None


def test_check_ocsp_signature_wrong_cert(pki):
    helper = _helper(pki)
    with pytest.raises(OcspException, match="not valid"):
        helper.check_ocsp_signature(pki["leaf"], _response(pki))


def test_wrong_certificate_id_rejected(pki):
    helper = _helper(pki)
    with pytest.raises(OcspException, match="serial number"):
        helper.verify_ocsp_response(_response(pki, cert=pki["other_leaf"]))


def test_wrong_issuer_hash_rejected(pki):
    other_ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    other_ca = _issue("Other CA", other_ca_key, _name("Other CA"), other_ca_key, ca=True)
    helper = OcspHelper(pki["leaf"], None, other_ca, [other_ca], URL)
    single = next(iter(_response(pki).responses))
    with pytest.raises(OcspException, match="CertID does not match the issuer"):
        helper.check_certificate_id(single)


def test_stale_response_rejected(pki):
    helper = _helper(pki)
    resp = _response(
        pki,
        this_update=_now() - _dt.timedelta(days=3),
        next_update=_now() - _dt.timedelta(days=2),
    )
    with pytest.raises(OcspException, match="current date > nextUpdate"):
        helper.verify_ocsp_response(resp)


def test_future_response_rejected(pki):
    helper = _helper(pki)
    resp = _response(
        pki,
        this_update=_now() + _dt.timedelta(hours=1),
        next_update=_now() + _dt.timedelta(hours=2),
    )
    with pytest.raises(OcspException, match="current date < thisUpdate"):
        helper.verify_ocsp_response(resp)


def test_missing_next_update_rejected(pki):
    helper = _helper(pki)
    with pytest.raises(OcspException, match="nextUpdate field is missing"):
        helper.verify_ocsp_response(_response(pki, next_update=None))


def test_nonce_mismatch_rejected(pki):
    helper = _helper(pki)
    helper.create16_bytes_nonce()
    with pytest.raises(OcspException, match="Different nonce"):
        helper.verify_ocsp_response(_response(pki, nonce=b"\x01" * 16))


def test_nonce_in_response_without_request_nonce_rejected(pki):
    helper = _helper(pki)
    with pytest.raises(OcspException, match="Different nonce"):
        helper.check_nonce(_response(pki, nonce=b"\x01" * 16))


def test_missing_nonce_falls_back_to_time(pki):
    helper = _helper(pki)
    helper.create16_bytes_nonce()
    assert helper.check_nonce(_response(pki)) is False


def test_delegated_responder_without_ocsp_signing_eku_rejected(pki):
    key = ec.generate_private_key(ec.SECP256R1())
    responder = _responder(pki, key, eku=[ExtendedKeyUsageOID.SERVER_AUTH])
    helper = _helper(pki)
    with pytest.raises(OcspException, match="OCSPSigning"):
        helper.verify_ocsp_response(
            _response(pki, responder_cert=responder, signing_key=key)
        )


def test_delegated_responder_without_eku_extension_rejected(pki):
    key = ec.generate_private_key(ec.SECP256R1())
    responder = _responder(pki, key)
    helper = _helper(pki)
    with pytest.raises(OcspException, match="OCSPSigning"):
        helper.check_responder_cert(responder)


def test_responder_not_issued_by_issuer_rejected(pki):
    rogue_key = ec.generate_private_key(ec.SECP256R1())
    rogue = _issue(
        "Rogue Responder", rogue_key, _name("Rogue Responder"), rogue_key,
        ocsp_signing=True,
    )
    helper = _helper(pki)
    with pytest.raises(OcspException, match="not issued by"):
        helper.verify_ocsp_response(
            _response(pki, responder_cert=rogue, signing_key=rogue_key)
        )


def test_unknown_responder_rejected(pki):
    helper = _helper(pki, additional=[])
    with pytest.raises(OcspException, match="not found"):
        helper.verify_ocsp_response(_response(pki, include_certs=False))


# ---------------------------------------------------------------------------
# perform_request / get_response_ocsp (monkeypatched transport)
# ---------------------------------------------------------------------------


class _FakeHttpResponse:
    def __init__(self, code, body=b"", headers=None, reason="OK"):
        self._code = code
        self._body = io.BytesIO(body)
        self.headers = email.message.Message()
        for key, value in (headers or {}).items():
            self.headers[key] = value
        self.reason = reason
        self.closed = False

    def getcode(self):
        return self._code

    def read(self):
        return self._body.read()

    def close(self):
        self.closed = True


def test_perform_request_posts_ocsp_request(pki, monkeypatch):
    seen = []

    def _open(request):
        seen.append(request)
        return _FakeHttpResponse(200, b"DER")

    monkeypatch.setattr(ocsp_mod, "_open_url", _open)
    helper = _helper(pki)
    assert helper.perform_request(URL) == b"DER"
    (request,) = seen
    assert request.get_method() == "POST"
    assert request.full_url == URL
    assert request.get_header("Content-type") == "application/ocsp-request"
    assert request.get_header("Accept") == "application/ocsp-response"
    parsed = ocsp.load_der_ocsp_request(request.data)
    assert parsed.serial_number == pki["leaf"].serial_number
    assert parsed.extensions.get_extension_for_class(x509.OCSPNonce).value.nonce == (
        helper.get_nonce()
    )


def test_perform_request_follows_http_to_https_upgrade(pki, monkeypatch):
    urls = []

    def _open(request):
        urls.append(request.full_url)
        if request.full_url.startswith("http://"):
            return _FakeHttpResponse(
                301, headers={"Location": "https://ocsp.test.invalid/check"}
            )
        return _FakeHttpResponse(200, b"OK")

    monkeypatch.setattr(ocsp_mod, "_open_url", _open)
    assert _helper(pki).perform_request(URL) == b"OK"
    assert urls == [URL, "https://ocsp.test.invalid/check"]


def test_perform_request_ignores_other_redirects(pki, monkeypatch):
    urls = []

    def _open(request):
        urls.append(request.full_url)
        return _FakeHttpResponse(
            302, headers={"Location": "https://evil.invalid/check"}, reason="Found"
        )

    monkeypatch.setattr(ocsp_mod, "_open_url", _open)
    with pytest.raises(OSError, match="ResponseCode 302"):
        _helper(pki).perform_request(URL)
    assert urls == [URL]


def test_perform_request_non_200_raises(pki, monkeypatch):
    response = _FakeHttpResponse(500, reason="Server Error")
    monkeypatch.setattr(ocsp_mod, "_open_url", lambda request: response)
    with pytest.raises(OSError, match="ResponseCode 500: Server Error"):
        _helper(pki).perform_request(URL)
    assert response.closed


def test_perform_request_rejects_non_http_scheme(pki, monkeypatch):
    def _open(request):  # pragma: no cover - must not be reached
        raise AssertionError("should not open")

    monkeypatch.setattr(ocsp_mod, "_open_url", _open)
    with pytest.raises(OSError, match="unsupported URL scheme"):
        _helper(pki).perform_request("file:///etc/passwd")


def _responder_server(pki, **response_kwargs):
    """Fake transport that answers with the request's nonce echoed back."""

    def _open(request):
        req = ocsp.load_der_ocsp_request(request.data)
        nonce = req.extensions.get_extension_for_class(x509.OCSPNonce).value.nonce
        resp = _response(pki, nonce=nonce, **response_kwargs)
        from cryptography.hazmat.primitives import serialization

        return _FakeHttpResponse(200, resp.public_bytes(serialization.Encoding.DER))

    return _open


def test_get_response_ocsp_end_to_end(pki, monkeypatch):
    monkeypatch.setattr(ocsp_mod, "_open_url", _responder_server(pki))
    helper = _helper(pki)
    resp = helper.get_response_ocsp()
    assert resp.response_status == ocsp.OCSPResponseStatus.SUCCESSFUL
    assert helper.get_ocsp_responder_certificate() == pki["ca"]


def test_get_response_ocsp_unparseable_body(pki, monkeypatch):
    monkeypatch.setattr(
        ocsp_mod, "_open_url", lambda request: _FakeHttpResponse(200, b"garbage")
    )
    with pytest.raises(OSError, match="could not parse"):
        _helper(pki).get_response_ocsp()


def test_open_url_returns_http_error_instead_of_following(monkeypatch):
    import urllib.error
    import urllib.request

    class _Opener:
        def open(self, request):
            raise urllib.error.HTTPError(
                request.full_url, 302, "Found", email.message.Message(), None
            )

    monkeypatch.undo()  # restore the real _open_url
    monkeypatch.setattr(urllib.request, "build_opener", lambda *handlers: _Opener())
    req = urllib.request.Request(URL, data=b"x", method="POST")
    result = ocsp_mod._open_url(req)
    assert result.getcode() == 302


# ---------------------------------------------------------------------------
# CertificateVerifier.verify_ocsp (responder trust, id-pkix-ocsp-nocheck)
# ---------------------------------------------------------------------------


def test_verify_ocsp_responder_with_nocheck_skips_chain(pki, monkeypatch):
    key = ec.generate_private_key(ec.SECP256R1())
    responder = _responder(pki, key, ocsp_signing=True, nocheck=True)
    monkeypatch.setattr(
        ocsp_mod,
        "_open_url",
        _responder_server(pki, responder_cert=responder, signing_key=key),
    )
    # No trust anchor at all: nocheck short-circuits the chain verification.
    helper = OcspHelper(pki["leaf"], None, pki["ca"], [], URL)
    CertificateVerifier.verify_ocsp(helper, [])


def test_verify_ocsp_responder_chain_verified(pki, monkeypatch):
    key = ec.generate_private_key(ec.SECP256R1())
    responder = _responder(pki, key, ocsp_signing=True)
    monkeypatch.setattr(
        ocsp_mod,
        "_open_url",
        _responder_server(pki, responder_cert=responder, signing_key=key),
    )
    helper = _helper(pki)
    CertificateVerifier.verify_ocsp(helper, [pki["ca"]])


def test_verify_ocsp_responder_chain_without_anchor_fails(pki, monkeypatch):
    key = ec.generate_private_key(ec.SECP256R1())
    responder = _responder(pki, key, ocsp_signing=True)
    monkeypatch.setattr(
        ocsp_mod,
        "_open_url",
        _responder_server(pki, responder_cert=responder, signing_key=key),
    )
    helper = OcspHelper(pki["leaf"], None, pki["ca"], [], URL)
    with pytest.raises(CertificateVerificationException):
        CertificateVerifier.verify_ocsp(helper, [])
