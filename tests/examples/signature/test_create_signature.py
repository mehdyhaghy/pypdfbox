"""Tests for ``CreateSignature``."""

from __future__ import annotations

import contextlib
import io

import pytest

import pypdfbox.examples.signature.create_signature as cs_mod
from pypdfbox.examples.signature.create_signature import CreateSignature
from pypdfbox.pdmodel.interactive.digitalsignature.pd_signature import PDSignature

# ---------------------------------------------------------------------------
# Constructor / inheritance
# ---------------------------------------------------------------------------


def test_create_signature_extends_base(pkcs12_bytes, tsa_password):
    signer = CreateSignature(pkcs12_bytes, tsa_password)
    assert signer.get_certificate_chain()


def test_has_sign_detached_methods(pkcs12_bytes, tsa_password):
    signer = CreateSignature(pkcs12_bytes, tsa_password)
    assert callable(signer.sign_detached)
    assert callable(signer.sign_detached_document)


# ---------------------------------------------------------------------------
# usage() / main()
# ---------------------------------------------------------------------------


def test_usage_writes_to_stderr(capsys):
    CreateSignature.usage()
    err = capsys.readouterr().err
    assert "CreateSignature" in err
    assert "pkcs12" in err.lower()


def test_main_too_few_args_raises_systemexit():
    with pytest.raises(SystemExit):
        CreateSignature.main(["only-one"])


def test_main_zero_args_raises_systemexit():
    with pytest.raises(SystemExit):
        CreateSignature.main([])


def test_main_parses_tsa_and_external_flags(monkeypatch, tmp_path, pkcs12_bytes):
    keystore = tmp_path / "keystore.p12"
    keystore.write_bytes(pkcs12_bytes)
    pdf = tmp_path / "in.pdf"
    pdf.write_bytes(b"%PDF-1.4\n%%EOF\n")

    captured = {}

    def fake_sign(self, in_file, out_file, tsa_url):
        captured["in"] = in_file
        captured["out"] = out_file
        captured["tsa"] = tsa_url
        captured["external"] = self.is_external_signing()

    monkeypatch.setattr(CreateSignature, "sign_detached", fake_sign, raising=True)

    CreateSignature.main([str(keystore), "hunter2", str(pdf), "-tsa", "http://t", "-e"])

    assert captured["tsa"] == "http://t"
    assert captured["external"] is True
    assert captured["in"].name == "in.pdf"
    assert captured["out"].name == "in_signed.pdf"


def test_main_parses_e_only(monkeypatch, tmp_path, pkcs12_bytes):
    keystore = tmp_path / "keystore.p12"
    keystore.write_bytes(pkcs12_bytes)
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"%PDF-1.4\n%%EOF\n")

    captured = {}

    def fake_sign(self, in_file, out_file, tsa_url):
        captured["tsa"] = tsa_url
        captured["external"] = self.is_external_signing()

    monkeypatch.setattr(CreateSignature, "sign_detached", fake_sign, raising=True)

    CreateSignature.main([str(keystore), "hunter2", str(pdf), "-e"])
    assert captured["tsa"] is None
    assert captured["external"] is True


def test_main_no_optional_flags(monkeypatch, tmp_path, pkcs12_bytes):
    keystore = tmp_path / "keystore.p12"
    keystore.write_bytes(pkcs12_bytes)
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"%PDF-1.4\n%%EOF\n")

    captured = {}

    def fake_sign(self, in_file, out_file, tsa_url):
        captured["tsa"] = tsa_url
        captured["external"] = self.is_external_signing()

    monkeypatch.setattr(CreateSignature, "sign_detached", fake_sign, raising=True)

    CreateSignature.main([str(keystore), "hunter2", str(pdf)])
    assert captured["tsa"] is None
    assert captured["external"] is False


# ---------------------------------------------------------------------------
# sign_detached — file I/O paths
# ---------------------------------------------------------------------------


def test_sign_detached_missing_file_raises(tmp_path, pkcs12_bytes, tsa_password):
    signer = CreateSignature(pkcs12_bytes, tsa_password)
    with pytest.raises(FileNotFoundError, match="does not exist"):
        signer.sign_detached(tmp_path / "missing.pdf")


def test_sign_detached_uses_in_place_when_no_out_file(
    monkeypatch, tmp_path, pkcs12_bytes, tsa_password
):
    in_pdf = tmp_path / "input.pdf"
    in_pdf.write_bytes(b"%PDF-1.4\n%%EOF\n")

    captured = {}

    class FakeDoc:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    @contextlib.contextmanager
    def fake_load(_fh):
        yield FakeDoc()

    # ``Loader.load_pdf`` is used as a context manager inside sign_detached;
    # we replace it with a context-manager factory that yields a stub doc.
    class FakeLoader:
        @staticmethod
        def load_pdf(_fh):
            return FakeDoc()

    monkeypatch.setattr("pypdfbox.loader.Loader", FakeLoader)

    def fake_sign_doc(self, document, output):
        captured["doc"] = document
        captured["output"] = output

    monkeypatch.setattr(
        CreateSignature, "sign_detached_document", fake_sign_doc, raising=True
    )

    signer = CreateSignature(pkcs12_bytes, tsa_password)
    signer.sign_detached(in_pdf, tsa_url="http://tsa.test.invalid")
    assert isinstance(captured["doc"], FakeDoc)
    assert signer._tsa_url == "http://tsa.test.invalid"


def test_sign_detached_writes_to_explicit_out_file(
    monkeypatch, tmp_path, pkcs12_bytes, tsa_password
):
    in_pdf = tmp_path / "input.pdf"
    in_pdf.write_bytes(b"%PDF-1.4\n%%EOF\n")
    out_pdf = tmp_path / "out.pdf"

    class FakeDoc:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    class FakeLoader:
        @staticmethod
        def load_pdf(_fh):
            return FakeDoc()

    monkeypatch.setattr("pypdfbox.loader.Loader", FakeLoader)

    captured = {}

    def fake_sign_doc(self, document, output):
        captured["output_name"] = getattr(output, "name", None)
        output.write(b"SIGNED")

    monkeypatch.setattr(
        CreateSignature, "sign_detached_document", fake_sign_doc, raising=True
    )

    signer = CreateSignature(pkcs12_bytes, tsa_password)
    signer.sign_detached(in_pdf, out_pdf, tsa_url=None)
    assert out_pdf.read_bytes() == b"SIGNED"


# ---------------------------------------------------------------------------
# sign_detached_document — control flow
# ---------------------------------------------------------------------------


class _FakeDocument:
    """Minimal stand-in for a PDDocument with the methods exercised here."""

    def __init__(self):
        self.signatures = []
        self.incremental_calls = 0
        self.external_calls = 0
        self._external = None

    def add_signature(self, signature, *args):
        self.signatures.append(signature)

    def save_incremental(self, output):
        self.incremental_calls += 1
        output.write(b"INC")

    def save_incremental_for_external_signing(self, output):
        self.external_calls += 1
        self._external = _FakeExternal(output)
        return self._external


class _FakeExternal:
    def __init__(self, output):
        self.output = output
        self.signature_bytes = None

    def get_content(self):
        return io.BytesIO(b"to-be-signed")

    def set_signature(self, sig_bytes):
        self.signature_bytes = sig_bytes


def test_sign_detached_document_raises_when_mdp_is_one(
    monkeypatch, pkcs12_bytes, tsa_password
):
    signer = CreateSignature(pkcs12_bytes, tsa_password)
    monkeypatch.setattr(cs_mod.SigUtils, "get_mdp_permission", staticmethod(lambda d: 1))

    with pytest.raises(RuntimeError, match="No changes"):
        signer.sign_detached_document(_FakeDocument(), io.BytesIO())


def test_sign_detached_document_internal_signing(
    monkeypatch, pkcs12_bytes, tsa_password
):
    signer = CreateSignature(pkcs12_bytes, tsa_password)
    monkeypatch.setattr(cs_mod.SigUtils, "get_mdp_permission", staticmethod(lambda d: 0))
    set_calls = []
    monkeypatch.setattr(
        cs_mod.SigUtils,
        "set_mdp_permission",
        staticmethod(lambda d, s, p: set_calls.append((d, s, p))),
    )

    doc = _FakeDocument()
    out = io.BytesIO()
    signer.sign_detached_document(doc, out)

    # Internal signing path: add_signature called once + save_incremental.
    assert len(doc.signatures) == 1
    assert isinstance(doc.signatures[0], PDSignature)
    assert doc.incremental_calls == 1
    # mdp == 0 path triggers set_mdp_permission(doc, sig, 2).
    assert set_calls and set_calls[0][2] == 2
    # signature carries the canonical Filter / SubFilter / metadata
    sig = doc.signatures[0]
    assert sig.get_filter() == PDSignature.FILTER_ADOBE_PPKLITE
    assert sig.get_sub_filter() == PDSignature.SUBFILTER_ADBE_PKCS7_DETACHED
    assert sig.get_name() == "Example User"
    assert sig.get_location() == "Los Angeles, CA"
    assert sig.get_reason() == "Testing"


def test_sign_detached_document_external_signing(
    monkeypatch, pkcs12_bytes, tsa_password
):
    signer = CreateSignature(pkcs12_bytes, tsa_password)
    signer.set_external_signing(True)
    monkeypatch.setattr(cs_mod.SigUtils, "get_mdp_permission", staticmethod(lambda d: 2))
    # Stub the PKCS#7 signing to avoid the cryptography overhead.
    monkeypatch.setattr(
        signer, "sign", lambda content: b"PKCS7-BLOB-" + content.read()
    )

    doc = _FakeDocument()
    out = io.BytesIO()
    signer.sign_detached_document(doc, out)

    assert doc.external_calls == 1
    assert doc.incremental_calls == 0
    assert doc._external is not None
    assert doc._external.signature_bytes == b"PKCS7-BLOB-to-be-signed"


def test_sign_detached_document_mdp_zero_sets_permission(
    monkeypatch, pkcs12_bytes, tsa_password
):
    """When MDP is 0 (no existing perms) the helper assigns level 2."""
    signer = CreateSignature(pkcs12_bytes, tsa_password)
    monkeypatch.setattr(cs_mod.SigUtils, "get_mdp_permission", staticmethod(lambda d: 0))
    recorded = []
    monkeypatch.setattr(
        cs_mod.SigUtils,
        "set_mdp_permission",
        staticmethod(lambda d, sig, p: recorded.append(p)),
    )

    signer.sign_detached_document(_FakeDocument(), io.BytesIO())
    assert recorded == [2]


def test_sign_detached_document_mdp_two_skips_set_permission(
    monkeypatch, pkcs12_bytes, tsa_password
):
    """When MDP is already non-zero (e.g. 2) set_mdp_permission is NOT called."""
    signer = CreateSignature(pkcs12_bytes, tsa_password)
    monkeypatch.setattr(cs_mod.SigUtils, "get_mdp_permission", staticmethod(lambda d: 2))
    called = []
    monkeypatch.setattr(
        cs_mod.SigUtils,
        "set_mdp_permission",
        staticmethod(lambda *a: called.append(a)),
    )

    signer.sign_detached_document(_FakeDocument(), io.BytesIO())
    assert called == []
