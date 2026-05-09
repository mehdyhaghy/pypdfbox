from __future__ import annotations

import hashlib

import pytest
from cryptography.x509 import ExtensionNotFound

from pypdfbox.pdmodel.interactive.digitalsignature import sig_utils
from pypdfbox.pdmodel.interactive.digitalsignature.pd_signature import PDSignature


class _Extensions:
    def __init__(self, value: object | None) -> None:
        self._value = value

    def get_extension_for_oid(self, oid: object) -> object:
        if self._value is None:
            raise ExtensionNotFound("missing", oid)
        return type("Extension", (), {"value": self._value})()


class _Certificate:
    def __init__(self, eku_oids: list[str] | None) -> None:
        usages = [type("Usage", (), {"dotted_string": oid})() for oid in eku_oids or []]
        self.extensions = _Extensions(usages if eku_oids is not None else None)


def test_get_signed_data_rejects_negative_range_length() -> None:
    sig = PDSignature()
    sig.set_byte_range([0, 4, 8, -1])

    assert sig.get_signed_data(b"HEADxxxxTAIL") is None


def test_verify_reports_missing_contents_after_valid_byte_range() -> None:
    sig = PDSignature()
    sig.set_byte_range([0, 4, 8, 4])

    result = sig.verify(b"HEADxxxxTAIL")

    assert result.is_valid is False
    assert result.errors == ["missing /Contents"]
    assert result.computed_digest is None


def test_verify_uses_sha1_for_legacy_pkcs7_sha1_subfilter() -> None:
    sig = PDSignature()
    sig.set_byte_range([0, 4, 8, 4])
    sig.set_sub_filter(PDSignature.SUBFILTER_ADBE_PKCS7_SHA1)
    sig.set_contents(b"not-pkcs7")

    result = sig.verify(b"HEADxxxxTAIL")

    assert result.is_valid is False
    assert result.computed_digest == hashlib.sha1(b"HEADTAIL").digest()  # noqa: S324
    assert result.errors[0].startswith("failed to parse PKCS#7 /Contents")


def test_has_extended_key_usage_reports_absent_wrong_and_matching_usage() -> None:
    oid = "1.3.6.1.5.5.7.3.8"

    assert sig_utils._has_extended_key_usage(_Certificate(None), oid) is False  # noqa: SLF001
    assert sig_utils._has_extended_key_usage(_Certificate(["1.2.3.4"]), oid) is False  # noqa: SLF001
    assert sig_utils._has_extended_key_usage(_Certificate([oid]), oid) is True  # noqa: SLF001


def test_der_length_helper_rejects_eof() -> None:
    with pytest.raises(ValueError, match="unexpected EOF"):
        sig_utils._read_der_length(b"", 0)  # noqa: SLF001


def test_extract_pkcs7_message_digest_returns_none_when_set_extends_past_buffer() -> None:
    oid_der = bytes.fromhex("06092A864886F70D010904")

    assert sig_utils.extract_pkcs7_message_digest(oid_der + b"\x31\x05abc") is None
