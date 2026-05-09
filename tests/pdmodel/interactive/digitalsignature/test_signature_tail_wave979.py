from __future__ import annotations

import io
from typing import Any

from pypdfbox.pdmodel.interactive.digitalsignature import pkcs7_signature
from pypdfbox.pdmodel.interactive.digitalsignature.pkcs7_signature import (
    Pkcs7Signature,
)


def test_pkcs7_signature_preserves_additional_certificate_order(monkeypatch) -> None:
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
                calls.setdefault("extras", []).append(certificate)
                return self

            def sign(self, encoding: object, options: list[object]) -> bytes:
                calls["encoding"] = encoding
                calls["options"] = options
                return b"ordered"

    monkeypatch.setattr(
        pkcs7_signature,
        "_import_cryptography",
        lambda: (FakeHashes, FakeSerialization, FakePkcs7),
    )

    extra_one = object()
    extra_two = object()
    signer = Pkcs7Signature(
        object(),
        object(),
        additional_certificates=[extra_one, extra_two],
    )

    assert signer.sign(io.BytesIO(b"payload")) == b"ordered"
    assert calls["extras"] == [extra_one, extra_two]
    assert calls["data"] == b"payload"
