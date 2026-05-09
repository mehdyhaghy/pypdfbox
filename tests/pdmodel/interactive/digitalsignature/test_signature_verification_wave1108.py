from __future__ import annotations

from typing import Any

import pytest

from pypdfbox.pdmodel.interactive import digitalsignature
from tests.pdmodel.interactive.digitalsignature import (
    test_signature_verification as verification,
)


class _OversizedPkcs7Signature:
    def __init__(self, cert: object, key: object) -> None:
        self.cert = cert
        self.key = key

    def sign(self, stream: Any) -> bytes:
        assert stream.read()
        return b"x" * 4097


def test_real_pkcs7_roundtrip_placeholder_guard_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(verification, "_make_self_signed_signer", lambda: (object(), object()))
    monkeypatch.setattr(digitalsignature, "Pkcs7Signature", _OversizedPkcs7Signature)

    with pytest.raises(AssertionError, match="placeholder too small"):
        verification.test_verify_digest_match_against_real_pkcs7_blob()
