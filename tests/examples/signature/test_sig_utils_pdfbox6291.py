"""Hand-written tests for the PDFBOX-6291 ``SigUtils`` changes and the
PDFBOX-6289 example-side fixes. URL fetches are mocked (no network)."""

import io
import logging

import pytest

import pypdfbox.examples.signature.sig_utils as sig_utils_mod
from pypdfbox.cos.cos_dictionary import COSDictionary
from pypdfbox.cos.cos_name import COSName
from pypdfbox.examples.signature.create_signature import CreateSignature
from pypdfbox.examples.signature.sig_utils import SigUtils
from pypdfbox.examples.util.connected_input_stream import ConnectedInputStream
from pypdfbox.pdmodel import PDPage
from pypdfbox.pdmodel.interactive.digitalsignature.pd_signature import PDSignature
from pypdfbox.pdmodel.pd_document import PDDocument

_ALLOWED_HTTP = "http://www.freetsa.org/tsa.crt"
_ALLOWED_HTTPS_TARGET = "https://www.freetsa.org/tsa.crt"


class _FakeResponse(io.BytesIO):
    """Stands in for an ``http.client.HTTPResponse`` / ``HTTPError``."""

    def __init__(self, code, body=b"", headers=None, reason="OK"):
        super().__init__(body)
        self.code = code
        self.headers = headers or {}
        self.reason = reason
        self.close_count = 0

    def getcode(self):
        return self.code

    def close(self):
        self.close_count += 1
        super().close()


@pytest.fixture
def fake_open(monkeypatch):
    """Route ``_open_uri`` through a queue of canned responses."""
    calls: list[tuple[str, float]] = []
    queue: list[_FakeResponse] = []

    def _open(url, timeout):
        calls.append((url, timeout))
        return queue.pop(0)

    monkeypatch.setattr(sig_utils_mod, "_open_uri", _open)
    return calls, queue


# ---------- scheme check (b84f8d7d) ----------


@pytest.mark.parametrize(
    "url",
    [
        "ftp://www.freetsa.org/tsa.crt",
        "file:///etc/passwd",
        "httpx://www.freetsa.org/tsa.crt",
        "HTTP://www.freetsa.org/tsa.crt",
        "ldap://x500.gov.si/cn=SI-TRUST%20Root",
    ],
    ids=["ftp", "file", "httpx", "upper", "ldap"],
)
def test_open_url_rejects_other_schemes(url, fake_open):
    calls, _ = fake_open
    scheme = url.split(":", 1)[0]
    with pytest.raises(OSError, match=f"^{scheme} scheme not supported$"):
        SigUtils.open_url(url)
    assert calls == []


def test_open_url_without_scheme_is_rejected(fake_open):
    with pytest.raises(OSError, match="None scheme not supported"):
        SigUtils.open_url("www.freetsa.org/tsa.crt")


def test_check_access_uses_the_allow_list():
    SigUtils.check_access(_ALLOWED_HTTP)
    with pytest.raises(OSError, match="not in ALLOW_URL_SET"):
        SigUtils.check_access("http://evil.example/tsa.crt")


# ---------- fetch, redirects, timeouts, leaks ----------


def test_open_url_returns_connected_stream_with_timeout(fake_open):
    calls, queue = fake_open
    response = _FakeResponse(200, b"payload")
    queue.append(response)
    stream = SigUtils.open_url(_ALLOWED_HTTP)
    assert isinstance(stream, ConnectedInputStream)
    buf = bytearray(16)
    assert stream.read(buf) == 7
    assert bytes(buf[:7]) == b"payload"
    stream.close()
    assert response.closed
    assert calls == [(_ALLOWED_HTTP, SigUtils.READ_TIMEOUT_MS / 1000)]


@pytest.mark.parametrize("code", [301, 302, 303, 307, 308])
def test_open_url_follows_http_to_https_redirect(code, fake_open):
    calls, queue = fake_open
    first = _FakeResponse(code, headers={"Location": _ALLOWED_HTTPS_TARGET})
    second = _FakeResponse(200, b"cert")
    queue.extend([first, second])
    stream = SigUtils.open_url(_ALLOWED_HTTP)
    assert [url for url, _ in calls] == [_ALLOWED_HTTP, _ALLOWED_HTTPS_TARGET]
    assert first.closed
    assert stream.is_.read() == b"cert"
    stream.close()


def test_open_url_redirect_without_location_is_ignored(fake_open, caplog):
    calls, queue = fake_open
    queue.append(_FakeResponse(302, b"moved"))
    with caplog.at_level(logging.INFO, logger=sig_utils_mod.__name__):
        stream = SigUtils.open_url(_ALLOWED_HTTP)
    assert len(calls) == 1
    assert "redirection to None ignored" in caplog.text
    stream.close()


def test_open_url_redirect_to_other_url_is_ignored(fake_open):
    calls, queue = fake_open
    queue.append(
        _FakeResponse(302, b"", headers={"Location": "https://evil.example/tsa.crt"})
    )
    SigUtils.open_url(_ALLOWED_HTTP).close()
    assert len(calls) == 1


def test_open_url_error_status_closes_the_connection(fake_open):
    _, queue = fake_open
    response = _FakeResponse(404, b"", reason="Not Found")
    queue.append(response)
    with pytest.raises(OSError, match="404"):
        SigUtils.open_url(_ALLOWED_HTTP)
    assert response.close_count == 1


def test_open_url_failure_after_redirect_closes_the_second_connection(fake_open):
    _, queue = fake_open
    first = _FakeResponse(301, headers={"Location": _ALLOWED_HTTPS_TARGET})
    second = _FakeResponse(500, reason="Server Error")
    queue.extend([first, second])
    with pytest.raises(OSError, match="500"):
        SigUtils.open_url(_ALLOWED_HTTP)
    assert first.closed
    assert second.close_count == 1


def test_open_url_closes_connection_when_reading_the_status_fails(fake_open):
    _, queue = fake_open

    class Broken(_FakeResponse):
        def getcode(self):
            raise OSError("connection reset")

    response = Broken(200)
    queue.append(response)
    with pytest.raises(OSError, match="connection reset"):
        SigUtils.open_url(_ALLOWED_HTTP)
    assert response.close_count == 1


def test_open_url_is_blocked_by_the_suite_network_guard():
    with pytest.raises(OSError):
        SigUtils.open_url(_ALLOWED_HTTP)


# ---------- set_mdp_permission (3b6b9b8c) ----------


@pytest.mark.parametrize("permissions", [0, 4, -1])
def test_set_mdp_permission_rejects_invalid_values(permissions):
    doc = PDDocument()
    try:
        signature = PDSignature()
        with pytest.raises(ValueError, match="must be 1, 2 or 3"):
            SigUtils.set_mdp_permission(doc, signature, permissions)
        assert not signature.get_cos_object().contains_key(COSName.REFERENCE)
    finally:
        doc.close()


def test_set_mdp_permission_stores_the_signature_dictionary():
    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        signature = PDSignature()
        SigUtils.set_mdp_permission(doc, signature, permissions=2)
        perms = doc.get_document_catalog().get_cos_object().get_cos_dictionary(
            COSName.PERMS
        )
        stored = perms.get_dictionary_object(COSName.DOCMDP)
        assert isinstance(stored, COSDictionary)
        assert stored is signature.get_cos_object()
        assert SigUtils.get_mdp_permission(doc) == 2
    finally:
        doc.close()


# ---------- get_last_relevant_signature (d5b856c1) ----------


def test_get_last_relevant_signature_warns_about_unknown_type(caplog):
    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        signature = PDSignature()
        signature.set_byte_range([0, 1, 2, 100])
        signature.get_cos_object().set_item(
            COSName.TYPE, COSName.get_pdf_name("Bogus")
        )
        doc.add_signature(signature)
        with caplog.at_level(logging.WARNING, logger=sig_utils_mod.__name__):
            assert SigUtils.get_last_relevant_signature(doc) is None
        assert "Signature with unknown type ignored" in caplog.text
    finally:
        doc.close()


# ---------- PDFBOX-6289: password parameter, DER, unencrypted placeholder ----


def test_sign_detached_passes_the_password(monkeypatch, tmp_path, pkcs12_bytes, tsa_password):
    seen = {}
    real_load = PDDocument.load

    def load(source, password=None):
        seen["password"] = password
        return real_load(source, password)

    monkeypatch.setattr(PDDocument, "load", staticmethod(load))
    monkeypatch.setattr(
        CreateSignature, "sign_detached_document", lambda self, doc, out: None
    )
    src = tmp_path / "in.pdf"
    with PDDocument() as doc:
        doc.add_page(PDPage())
        doc.save(str(src))
    signer = CreateSignature(pkcs12_bytes, tsa_password)
    signer.sign_detached(src, tmp_path / "out.pdf", None, "secret")
    assert seen["password"] == "secret"
    signer.sign_detached(src, tmp_path / "out2.pdf")
    assert seen["password"] is None


def test_internal_signing_signs_the_exact_byte_range(tmp_path, pkcs12_bytes, tsa_password):
    """The CMS messageDigest is the digest of the signed bytes as they are
    (PKCS7 Binary), also for content with line feeds."""
    import hashlib

    from pypdfbox.pdmodel.interactive.digitalsignature.sig_utils import (
        extract_pkcs7_message_digest,
        strip_signature_padding,
    )

    src = tmp_path / "in.pdf"
    with PDDocument() as doc:
        doc.add_page(PDPage())
        doc.save(str(src))
    out = tmp_path / "signed.pdf"
    CreateSignature(pkcs12_bytes, tsa_password).sign_detached(src, out)
    raw = out.read_bytes()
    assert b"\n" in raw
    with PDDocument.load(str(out)) as doc:
        sig = doc.get_last_signature_dictionary()
        byte_range = sig.get_byte_range()
        signed = (
            raw[byte_range[0] : byte_range[0] + byte_range[1]]
            + raw[byte_range[2] : byte_range[2] + byte_range[3]]
        )
        blob = strip_signature_padding(sig.get_contents())
        # DER SignedData: SEQUENCE with a definite length
        assert blob[0] == 0x30 and blob[1] != 0x80
        assert extract_pkcs7_message_digest(blob) == hashlib.sha256(signed).digest()
