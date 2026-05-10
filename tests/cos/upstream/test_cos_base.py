"""Parity translation of upstream ``TestCOSBase`` (PDFBox 3.0.x).

Upstream class: ``pdfbox/src/test/java/org/apache/pdfbox/cos/TestCOSBase.java``.

Java's ``TestCOSBase`` is abstract — the contract tests run via subclass
instances. Here we exercise the same contract on a concrete COS type
(``COSInteger``); the per-subclass parity tests live alongside their
specific suites.
"""

from __future__ import annotations

from pypdfbox.cos import COSInteger
from pypdfbox.cos.cos_object_key import COSObjectKey


def test_get_cos_object() -> None:
    # Mirrors testGetCOSObject (Java line 40): the underlying object is
    # returned by getCOSObject().
    test_cos_base = COSInteger(0)
    assert test_cos_base.get_cos_object() == test_cos_base


def test_is_set_direct() -> None:
    # Mirrors testIsSetDirect (Java line 54).
    test_cos_base = COSInteger(0)
    test_cos_base.set_direct(True)
    assert test_cos_base.is_direct()
    test_cos_base.set_direct(False)
    assert not test_cos_base.is_direct()


def test_get_set_key() -> None:
    # Covers getKey / setKey (Java lines 86, 96). Upstream lacks a
    # dedicated test method for these — the round-trip is exercised
    # implicitly by the parser. Asserted here to lock the contract.
    test_cos_base = COSInteger(0)
    assert test_cos_base.get_key() is None
    key = COSObjectKey(42, 0)
    test_cos_base.set_key(key)
    assert test_cos_base.get_key() is key
    test_cos_base.set_key(None)
    assert test_cos_base.get_key() is None
