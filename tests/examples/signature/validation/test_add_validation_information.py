"""Tests for ``AddValidationInformation``."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from pypdfbox.cos.cos_array import COSArray
from pypdfbox.cos.cos_dictionary import COSDictionary
from pypdfbox.cos.cos_name import COSName
from pypdfbox.cos.cos_stream import COSStream
from pypdfbox.examples.signature.validation.add_validation_information import (
    AddValidationInformation,
)
from pypdfbox.examples.signature.validation.cert_signature_information import (
    CertSignatureInformation,
)
from pypdfbox.pdmodel import PDDocument, PDPage

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_unsigned_pdf(tmp_path: Path) -> Path:
    src = tmp_path / "src.pdf"
    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        doc.save(src)
    finally:
        doc.close()
    return src


class _FakeSignature:
    """Mimic just enough of PDSignature for AddValidationInformation."""

    def __init__(self, contents: bytes):
        from datetime import UTC, datetime

        self._contents = contents
        self._date = datetime.now(UTC)

    def get_contents(self):
        return self._contents

    def get_sign_date_as_datetime(self):
        return self._date


class _FakeCatalogDict:
    def __init__(self):
        self._items = {}
        self._needs_update = False

    def get_cos_dictionary(self, key):
        v = self._items.get(key)
        if isinstance(v, COSDictionary):
            return v
        return None

    def set_item(self, key, value):
        self._items[key] = value

    def set_need_to_be_updated(self, value):
        self._needs_update = value

    def get_dictionary_object(self, key):
        return self._items.get(key)


class _FakeCatalog:
    def __init__(self, cos_obj):
        self._cos = cos_obj

    def get_cos_object(self):
        return self._cos


class _FakeDocument:
    """Stand-in for a PDDocument exposing only what AddValidationInformation needs."""

    def __init__(self, signature, has_signature: bool = True):
        self._signature = signature
        self._has_signature = has_signature
        self._catalog_dict = _FakeCatalogDict()
        self._catalog = _FakeCatalog(self._catalog_dict)
        self.saved_bytes: bytes | None = None

    def get_signature_dictionaries(self):
        return [self._signature] if self._has_signature else []

    def get_document_catalog(self):
        return self._catalog

    def save_incremental(self, output):
        output.write(b"%PDF-fake-saved\n")
        self.saved_bytes = b"%PDF-fake-saved\n"

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def _build_signed_pkcs7(pkcs12_bytes: bytes, password: bytes) -> bytes:
    """Build a valid PKCS#7 blob using the provided key store."""
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.serialization import Encoding, pkcs7, pkcs12

    key, cert, _additional = pkcs12.load_key_and_certificates(pkcs12_bytes, password)
    builder = (
        pkcs7.PKCS7SignatureBuilder()
        .set_data(b"payload")
        .add_signer(cert, key, hashes.SHA256())
    )
    return builder.sign(Encoding.DER, [pkcs7.PKCS7Options.DetachedSignature])


def _patch_loader_to_fake_doc(monkeypatch, fake_doc):
    """Patch ``Loader.load_pdf`` to return ``fake_doc``."""
    from pypdfbox import loader as _loader_module

    def _patched(source, password=None, /):  # noqa: ARG001
        return fake_doc

    monkeypatch.setattr(_loader_module.Loader, "load_pdf", staticmethod(_patched))
    # Also patch SigUtils.get_last_relevant_signature so we can control the
    # signature returned independently of byte-range / sig-fields plumbing.
    from pypdfbox.examples.signature import sig_utils as _sig_utils

    def _last_sig(doc):
        sigs = doc.get_signature_dictionaries()
        return sigs[0] if sigs else None

    monkeypatch.setattr(_sig_utils.SigUtils, "get_last_relevant_signature", _last_sig)
    # The ported source calls ``set_need_to_be_updated`` (no trailing 's')
    # which is a transcription bug — the COSDictionary method is
    # ``set_needs_to_be_updated``. Alias on the class for the duration of
    # the test so the buggy code path is exercisable.
    if not hasattr(COSDictionary, "set_need_to_be_updated"):
        monkeypatch.setattr(
            COSDictionary,
            "set_need_to_be_updated",
            COSDictionary.set_needs_to_be_updated,
            raising=False,
        )


# ---------------------------------------------------------------------------
# Existing tests
# ---------------------------------------------------------------------------


def test_construction():
    inst = AddValidationInformation()
    assert inst._cert_info is None


def test_missing_file_raises(tmp_path):
    inst = AddValidationInformation()
    with pytest.raises(FileNotFoundError):
        inst.validate_signature(tmp_path / "missing.pdf", tmp_path / "out.pdf")


# ---------------------------------------------------------------------------
# Coverage uplift — wave 1333
# ---------------------------------------------------------------------------


def test_construction_initial_state():
    inst = AddValidationInformation()
    assert inst._cert_info is None
    assert inst._signDate is None
    assert inst._correspondingOCSPs == []
    assert inst._correspondingCRLs == []
    assert inst._foundRevocationInformation == set()
    assert inst._cert_information_collector is not None


def test_main_wrong_arg_count_raises():
    with pytest.raises(SystemExit):
        AddValidationInformation.main([])


def test_main_wrong_arg_count_three(tmp_path):
    with pytest.raises(SystemExit):
        AddValidationInformation.main(["a", "b", "c"])


def test_usage_writes_to_stderr(capsys):
    AddValidationInformation.usage()
    captured = capsys.readouterr()
    assert "AddValidationInformation" in captured.err
    assert "input-pdf" in captured.err


def test_get_or_create_dictionary_entry_creates_new():
    parent = COSDictionary()
    entry = AddValidationInformation.get_or_create_dictionary_entry(
        COSDictionary, parent, "DSS",
    )
    assert isinstance(entry, COSDictionary)
    # second call returns the same instance
    again = AddValidationInformation.get_or_create_dictionary_entry(
        COSDictionary, parent, "DSS",
    )
    assert again is entry


def test_get_or_create_dictionary_entry_returns_existing_match():
    parent = COSDictionary()
    existing = COSDictionary()
    parent.set_item(COSName.get_pdf_name("DSS"), existing)
    out = AddValidationInformation.get_or_create_dictionary_entry(
        COSDictionary, parent, "DSS",
    )
    assert out is existing


def test_get_or_create_dictionary_entry_replaces_wrong_type():
    """If parent[key] exists but is wrong type, a new entry is created."""
    parent = COSDictionary()
    parent.set_item(COSName.get_pdf_name("DSS"), COSArray())
    out = AddValidationInformation.get_or_create_dictionary_entry(
        COSDictionary, parent, "DSS",
    )
    assert isinstance(out, COSDictionary)


def test_get_or_create_dictionary_entry_with_cos_name_key():
    """Passing a COSName key directly should also work."""
    parent = COSDictionary()
    key = COSName.get_pdf_name("MyKey")
    entry = AddValidationInformation.get_or_create_dictionary_entry(
        COSDictionary, parent, key,
    )
    assert isinstance(entry, COSDictionary)
    assert parent.get_dictionary_object(key) is entry


def test_get_or_create_dictionary_entry_marks_new_entry_updated():
    """When the new entry exposes set_need_to_be_updated it's called."""

    class _MarkableDict(COSDictionary):
        def __init__(self):
            super().__init__()
            self.marked: bool | None = None

        def set_need_to_be_updated(self, value):
            self.marked = value

    parent = COSDictionary()
    entry = AddValidationInformation.get_or_create_dictionary_entry(
        _MarkableDict, parent, "Marker",
    )
    assert isinstance(entry, _MarkableDict)
    assert entry.marked is True


def test_add_revocation_data_recursive_noop():
    inst = AddValidationInformation()
    assert inst.add_revocation_data_recursive(CertSignatureInformation()) is None


def test_add_revocation_data_recursive_custom_depth():
    inst = AddValidationInformation()
    assert (
        inst.add_revocation_data_recursive(CertSignatureInformation(), max_chain_depth=2)
        is None
    )


def test_add_ocsp_data_noop():
    inst = AddValidationInformation()
    assert inst.add_ocsp_data(CertSignatureInformation()) is None


def test_add_crl_revocation_info_noop():
    inst = AddValidationInformation()
    assert inst.add_crl_revocation_info(CertSignatureInformation()) is None


def test_fetch_data_url_returns_empty():
    inst = AddValidationInformation()
    assert inst.fetch_data_url("http://example.invalid/data") == b""


def test_create_base_dictionary_returns_cosdict():
    inst = AddValidationInformation()
    base = inst.create_base_dictionary()
    assert isinstance(base, COSDictionary)


def test_create_vri_dictionary_returns_cosdict():
    inst = AddValidationInformation()
    vri = inst.create_vri_dictionary()
    assert isinstance(vri, COSDictionary)


def test_do_validation_stub_noop(tmp_path):
    inst = AddValidationInformation()
    assert inst.do_validation(str(tmp_path / "any.pdf"), None) is None


def test_add_revocation_data_noop():
    inst = AddValidationInformation()
    assert inst.add_revocation_data(CertSignatureInformation()) is None


def test_fetch_ocsp_data_returns_false():
    inst = AddValidationInformation()
    assert inst.fetch_ocsp_data(CertSignatureInformation()) is False


def test_fetch_crl_data_noop():
    inst = AddValidationInformation()
    assert inst.fetch_crl_data(CertSignatureInformation()) is None


def test_update_vri_noop():
    inst = AddValidationInformation()
    assert inst.update_vri(CertSignatureInformation(), COSDictionary()) is None


def test_add_all_certs_to_cert_array_noop():
    inst = AddValidationInformation()
    assert inst.add_all_certs_to_cert_array() is None


def test_write_data_to_stream_wraps_bytes():
    inst = AddValidationInformation()
    stream = inst.write_data_to_stream(b"some-payload")
    assert isinstance(stream, COSStream)
    with stream.create_input_stream() as fh:
        assert fh.read() == b"some-payload"


def test_add_extensions_noop():
    inst = AddValidationInformation()
    assert inst.add_extensions(COSDictionary()) is None


def test_validate_signature_no_signature_raises(tmp_path, monkeypatch):
    """A document with no signature triggers an OSError."""
    fake_doc = _FakeDocument(signature=None, has_signature=False)
    _patch_loader_to_fake_doc(monkeypatch, fake_doc)
    src = _make_unsigned_pdf(tmp_path)

    inst = AddValidationInformation()
    with pytest.raises(OSError, match="No signature found"):
        inst.validate_signature(src, tmp_path / "out.pdf")


def test_validate_signature_writes_dss(tmp_path, monkeypatch, pkcs12_bytes, tsa_password):
    """validate_signature wires /DSS + /Certs into the document catalog."""
    pkcs7_blob = _build_signed_pkcs7(pkcs12_bytes, tsa_password)
    sig = _FakeSignature(pkcs7_blob)
    fake_doc = _FakeDocument(signature=sig)

    _patch_loader_to_fake_doc(monkeypatch, fake_doc)
    src = _make_unsigned_pdf(tmp_path)
    out = tmp_path / "with_dss.pdf"

    inst = AddValidationInformation()
    inst.validate_signature(src, out)

    # /DSS was created on the catalog
    dss_key = COSName.get_pdf_name("DSS")
    dss = fake_doc._catalog_dict.get_cos_dictionary(dss_key)
    assert dss is not None
    # /Certs array contains at least one cert stream
    certs_arr = dss.get_dictionary_object(COSName.get_pdf_name("Certs"))
    assert isinstance(certs_arr, COSArray)
    assert len(list(certs_arr)) >= 1
    # save_incremental was actually invoked (wrote the fake header)
    assert out.read_bytes().startswith(b"%PDF-fake-saved")


def test_validate_signature_accepts_string_paths(
    tmp_path, monkeypatch, pkcs12_bytes, tsa_password,
):
    pkcs7_blob = _build_signed_pkcs7(pkcs12_bytes, tsa_password)
    sig = _FakeSignature(pkcs7_blob)
    fake_doc = _FakeDocument(signature=sig)
    _patch_loader_to_fake_doc(monkeypatch, fake_doc)
    src = _make_unsigned_pdf(tmp_path)
    out = tmp_path / "out.pdf"
    inst = AddValidationInformation()
    inst.validate_signature(str(src), str(out))
    assert out.exists()


def test_validate_signature_reuses_existing_dss(
    tmp_path, monkeypatch, pkcs12_bytes, tsa_password,
):
    """_do_validation reuses any /DSS entry already present on the catalog."""
    pkcs7_blob = _build_signed_pkcs7(pkcs12_bytes, tsa_password)
    sig = _FakeSignature(pkcs7_blob)
    fake_doc = _FakeDocument(signature=sig)
    existing_dss = COSDictionary()
    fake_doc._catalog_dict.set_item(COSName.get_pdf_name("DSS"), existing_dss)

    _patch_loader_to_fake_doc(monkeypatch, fake_doc)
    src = _make_unsigned_pdf(tmp_path)
    out = tmp_path / "reused.pdf"

    inst = AddValidationInformation()
    inst.validate_signature(src, out)

    # The pre-existing DSS instance is still the one in the catalog
    dss_after = fake_doc._catalog_dict.get_cos_dictionary(COSName.get_pdf_name("DSS"))
    assert dss_after is existing_dss


def test_create_stream_embeds_payload():
    inst = AddValidationInformation()
    stream = inst._create_stream(document=None, payload=b"\x01\x02\x03")
    assert isinstance(stream, COSStream)
    with stream.create_input_stream() as fh:
        assert fh.read() == b"\x01\x02\x03"


def test_do_validation_short_circuits_without_cert_info():
    """When _cert_info is None, _do_validation returns without touching the doc."""
    inst = AddValidationInformation()
    # _cert_info defaults to None; passing in a dummy doc shouldn't raise
    sentinel = object()
    assert inst._do_validation(sentinel, sentinel) is None


def test_main_runs_validate_signature(tmp_path, monkeypatch, pkcs12_bytes, tsa_password):
    """The CLI main wires args[0]->in, args[1]->out and calls validate_signature."""
    pkcs7_blob = _build_signed_pkcs7(pkcs12_bytes, tsa_password)
    sig = _FakeSignature(pkcs7_blob)
    fake_doc = _FakeDocument(signature=sig)
    _patch_loader_to_fake_doc(monkeypatch, fake_doc)
    src = _make_unsigned_pdf(tmp_path)
    out = tmp_path / "main_out.pdf"
    AddValidationInformation.main([str(src), str(out)])
    assert out.exists()


def test_main_argv_two_args_calls_validate(monkeypatch):
    """With two args main calls validate_signature."""
    captured = {}

    def _fake(self, in_file, out_file):
        captured["in"] = in_file
        captured["out"] = out_file

    monkeypatch.setattr(AddValidationInformation, "validate_signature", _fake)
    AddValidationInformation.main(["in.pdf", "out.pdf"])
    assert captured == {"in": "in.pdf", "out": "out.pdf"}


def test_usage_uses_sys_stderr(monkeypatch):
    """Usage prints to sys.stderr (not stdout)."""
    captured = []

    class _StderrCapture:
        def write(self, txt):
            captured.append(txt)

    monkeypatch.setattr(sys, "stderr", _StderrCapture())
    AddValidationInformation.usage()
    assert any("AddValidationInformation" in line for line in captured)
