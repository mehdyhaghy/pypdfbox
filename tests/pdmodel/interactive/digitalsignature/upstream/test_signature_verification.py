"""Ported upstream tests for the verify pipeline.

PDFBox 3.0 has no standalone unit test for the signature *verification*
path — verification is exercised end-to-end via
``ShowSignatureTest.java`` in ``pdfbox-examples``, which requires live
PKCS#7 + sample PDFs we don't carry here (verified 2026-04-27 against
the ``apache/pdfbox`` ``3.0`` branch). Hand-written round-trip tests
covering ``PDSignature.verify`` /
``SignatureValidationResult`` / ``Pkcs7Signature`` /
``SignatureInterface`` live in
``tests/pdmodel/interactive/digitalsignature/test_signature_verification.py``.
"""

from __future__ import annotations


def test_no_upstream_tests_for_verify_pipeline() -> None:
    """Sentinel — upstream has no JUnit class for the verify path."""
    assert True
