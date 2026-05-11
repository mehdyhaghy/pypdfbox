"""Tests for ``CertInformationCollector``."""

from __future__ import annotations

import pytest

from pypdfbox.examples.signature.validation.cert_information_collector import (
    CertificateProccessingException,
    CertificateProcessingException,
    CertInformationCollector,
)
from pypdfbox.examples.signature.validation.cert_signature_information import (
    CertSignatureInformation,
)


def test_aliases_match():
    assert CertificateProccessingException is CertificateProcessingException


def test_construction():
    collector = CertInformationCollector()
    assert collector.get_certificate_set() == set()


def test_add_all_certs_from_holders(self_signed_cert):
    cert, _ = self_signed_cert
    collector = CertInformationCollector()
    collector.add_all_certs_from_holders([cert])
    assert cert in collector.get_certificate_set()


class _FakeSignature:
    def __init__(self, contents: bytes | None):
        self._contents = contents

    def get_contents(self):
        return self._contents


def test_get_last_cert_info_returns_none_when_no_contents():
    collector = CertInformationCollector()
    assert collector.get_last_cert_info(_FakeSignature(None)) is None


def test_get_last_cert_info_raises_on_bad_contents():
    collector = CertInformationCollector()
    with pytest.raises(CertificateProcessingException):
        collector.get_last_cert_info(_FakeSignature(b"not-pkcs7"))


def test_cert_signature_information_default_values():
    info = CertSignatureInformation()
    assert info.get_certificate() is None
