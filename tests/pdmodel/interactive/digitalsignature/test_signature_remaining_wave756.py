from __future__ import annotations

import io
from typing import Any

from pypdfbox.cos import COSArray, COSName, COSString
from pypdfbox.pdmodel.interactive.digitalsignature import (
    PDPropBuild,
    PDPropBuildDataDict,
    PDSeedValue,
    PDSignatureLock,
    pkcs7_signature,
)
from pypdfbox.pdmodel.interactive.digitalsignature.pkcs7_signature import (
    Pkcs7Signature,
)


def test_seed_value_sub_filter_returns_none_for_malformed_name_array() -> None:
    seed = PDSeedValue()
    seed.get_cos_object().set_item(
        "SubFilter",
        COSArray([COSString("adbe.pkcs7.detached")]),
    )

    assert seed.get_sub_filter() is None


def test_seed_value_reasons_returns_none_for_malformed_string_array() -> None:
    seed = PDSeedValue()
    seed.get_cos_object().set_item(
        "Reasons",
        COSArray([COSName.get_pdf_name("NotText")]),
    )

    assert seed.get_reasons() is None


def test_seed_value_set_legal_attestation_none_removes_entry() -> None:
    seed = PDSeedValue()
    seed.set_legal_attestation(["Accepted"])

    seed.set_legal_attestation(None)

    assert seed.get_legal_attestation() == []
    assert seed.has_legal_attestation() is False


def test_signature_lock_fields_returns_none_for_malformed_array() -> None:
    lock = PDSignatureLock()
    lock.get_cos_object().set_item(
        "Fields",
        COSArray([COSName.get_pdf_name("Signature1")]),
    )

    assert lock.get_fields() is None


def test_signature_lock_get_p_returns_none_for_non_integer() -> None:
    lock = PDSignatureLock()
    lock.get_cos_object().set_item("P", COSName.get_pdf_name("One"))

    assert lock.get_p() is None


def test_prop_build_set_pub_sec_none_removes_entry() -> None:
    prop_build = PDPropBuild()
    pub_sec = PDPropBuildDataDict()
    pub_sec.set_name("Adobe.PubSec")
    prop_build.set_pd_prop_build_pub_sec(pub_sec)

    prop_build.set_pd_prop_build_pub_sec(None)

    assert prop_build.get_pub_sec() is None
    assert prop_build.has_pub_sec() is False


def test_pkcs7_signature_exposes_certificate_and_adds_extra_certificates(
    monkeypatch,
) -> None:
    calls: dict[str, Any] = {}

    class FakeHashes:
        class SHA256:
            pass

    class FakeSerialization:
        class Encoding:
            DER = object()

    class FakePkcs7:
        class PKCS7Options:
            DetachedSignature = object()
            Binary = object()

        class PKCS7SignatureBuilder:
            def set_data(self, data: bytes) -> FakePkcs7.PKCS7SignatureBuilder:
                calls["data"] = data
                return self

            def add_signer(
                self,
                certificate: object,
                private_key: object,
                hash_algorithm: object,
            ) -> FakePkcs7.PKCS7SignatureBuilder:
                calls["signer"] = (certificate, private_key, hash_algorithm)
                return self

            def add_certificate(
                self,
                certificate: object,
            ) -> FakePkcs7.PKCS7SignatureBuilder:
                calls.setdefault("extra", []).append(certificate)
                return self

            def sign(self, encoding: object, options: list[object]) -> bytes:
                calls["encoding"] = encoding
                calls["options"] = options
                return b"pkcs7"

    monkeypatch.setattr(
        pkcs7_signature,
        "_import_cryptography",
        lambda: (FakeHashes, FakeSerialization, FakePkcs7),
    )
    certificate = object()
    private_key = object()
    extra = object()

    signer = Pkcs7Signature(
        certificate,
        private_key,
        additional_certificates=[extra],
    )

    assert signer.certificate is certificate
    assert signer.sign(io.BytesIO(b"document bytes")) == b"pkcs7"
    assert calls["data"] == b"document bytes"
    assert calls["signer"][0:2] == (certificate, private_key)
    assert calls["extra"] == [extra]
    assert calls["encoding"] is FakeSerialization.Encoding.DER
    assert calls["options"] == [
        FakePkcs7.PKCS7Options.DetachedSignature,
        FakePkcs7.PKCS7Options.Binary,
    ]
