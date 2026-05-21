"""Wave 1365 — coverage round-out for :class:`CertificateVerificationResult`.

The base test pair covers the success and failure constructors only;
this module adds: default-init invariants, ``result`` payload accepting
arbitrary types, ``exception`` overriding ``result`` when both are
provided, and ``is_valid``/``get_result``/``get_exception`` always
returning consistent tuples.
"""

from __future__ import annotations

from pypdfbox.examples.signature.cert.certificate_verification_result import (
    CertificateVerificationResult,
)


def test_default_construct_is_valid_with_no_payload() -> None:
    """Calling the ctor with no args triggers the success path with
    ``result=None`` (lines 27-29)."""
    result = CertificateVerificationResult()
    assert result.is_valid() is True
    assert result.get_result() is None
    assert result.get_exception() is None


def test_exception_overrides_result_argument() -> None:
    """When ``exception`` is supplied alongside ``result``, the failure
    branch wins (lines 22-25). The supplied payload must be discarded."""
    err = RuntimeError("boom")
    result = CertificateVerificationResult(result="payload", exception=err)
    assert result.is_valid() is False
    assert result.get_result() is None
    assert result.get_exception() is err


def test_result_accepts_dict_payload() -> None:
    """The ``result`` field is typed ``Any`` — verify a dict round-trips."""
    payload = {"chain": ["leaf", "root"], "trusted": True}
    result = CertificateVerificationResult(result=payload)
    assert result.get_result() is payload


def test_result_accepts_falsy_payload_keeps_valid() -> None:
    """A falsy result (empty list) must still be ``is_valid()`` —
    ``self._valid`` is set by ``exception is None``, not the truthiness
    of ``result`` (lines 22-29)."""
    result = CertificateVerificationResult(result=[])
    assert result.is_valid() is True
    assert result.get_result() == []


def test_chained_exception_preserved() -> None:
    """Nested exceptions are stored verbatim (no ``copy.deepcopy``-style
    rewrap)."""
    outer = OSError("upper")
    outer.__cause__ = ValueError("inner")
    result = CertificateVerificationResult(exception=outer)
    assert result.get_exception() is outer
    assert result.get_exception().__cause__ is outer.__cause__


def test_exception_only_constructor_has_no_result() -> None:
    """Failure path must zero out ``_result`` even if the caller
    accidentally also passed it (defensive check on lines 23-25)."""
    err = ValueError("x")
    result = CertificateVerificationResult(result=42, exception=err)
    assert result.get_result() is None


def test_two_instances_are_independent() -> None:
    """The ctor doesn't share mutable state across instances — a guard
    against ``mutable default arg``-style bugs."""
    a = CertificateVerificationResult(result=["a"])
    b = CertificateVerificationResult(result=["b"])
    assert a.get_result() == ["a"]
    assert b.get_result() == ["b"]
    a.get_result().append("z")
    assert b.get_result() == ["b"]
