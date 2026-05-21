"""Wave 1366 (agent B) — branch coverage for :class:`SigningSupport`.

``SigningSupport`` bridges a :class:`COSWriter` to an external CMS /
PKCS#7 signer (e.g. an HSM). The class is small (≈60 LOC) but bridges
the COS writer's "get-content / set-signature" half of the
``saveIncrementalForExternalSigning`` flow that pypdfbox surfaces via
:meth:`PDDocument.save_incremental_for_external_signing`. Most of the
control flow is in error paths that aren't otherwise exercised:

* :meth:`get_content` raises ``RuntimeError`` after :meth:`close`,
* :meth:`set_signature` raises ``RuntimeError`` after :meth:`close`,
* the context-manager flow auto-closes on exit even when the body
  raises,
* :meth:`close` is idempotent — calling it twice is a no-op.
"""

from __future__ import annotations

from io import BytesIO

import pytest

from pypdfbox.pdmodel.interactive.digitalsignature.signing_support import (
    SigningSupport,
)


class _FakeCOSWriter:
    """Minimal COSWriter shape used by :class:`SigningSupport`."""

    def __init__(self, payload: bytes) -> None:
        self._payload = payload
        self.installed_signature: bytes | None = None

    def get_data_to_sign(self) -> BytesIO:
        return BytesIO(self._payload)

    def write_external_signature(self, signature: bytes) -> None:
        self.installed_signature = signature


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_get_content_returns_unsigned_byte_stream() -> None:
    writer = _FakeCOSWriter(b"to-sign")
    support = SigningSupport(writer)  # type: ignore[arg-type]
    stream = support.get_content()
    assert stream.read() == b"to-sign"


def test_set_signature_installs_bytes_into_writer() -> None:
    writer = _FakeCOSWriter(b"unused")
    support = SigningSupport(writer)  # type: ignore[arg-type]
    support.set_signature(b"PKCS7-BLOB")
    assert writer.installed_signature == b"PKCS7-BLOB"


# ---------------------------------------------------------------------------
# Context manager
# ---------------------------------------------------------------------------


def test_context_manager_closes_on_normal_exit() -> None:
    writer = _FakeCOSWriter(b"data")
    with SigningSupport(writer) as support:  # type: ignore[arg-type]
        support.set_signature(b"sig")
    # ``support`` has been closed — subsequent calls must error.
    with pytest.raises(RuntimeError):
        support.set_signature(b"more")


def test_context_manager_closes_on_exception() -> None:
    """When the ``with`` body raises, :meth:`__exit__` still drops the
    COSWriter reference."""
    writer = _FakeCOSWriter(b"data")
    sentinel: SigningSupport | None = None
    try:
        with SigningSupport(writer) as support:  # type: ignore[arg-type]
            sentinel = support
            raise ValueError("boom from caller")
    except ValueError:
        pass
    assert sentinel is not None
    with pytest.raises(RuntimeError):
        sentinel.get_content()


# ---------------------------------------------------------------------------
# Closed-state guards
# ---------------------------------------------------------------------------


def test_get_content_raises_when_closed() -> None:
    writer = _FakeCOSWriter(b"data")
    support = SigningSupport(writer)  # type: ignore[arg-type]
    support.close()
    with pytest.raises(RuntimeError, match="closed"):
        support.get_content()


def test_set_signature_raises_when_closed() -> None:
    writer = _FakeCOSWriter(b"data")
    support = SigningSupport(writer)  # type: ignore[arg-type]
    support.close()
    with pytest.raises(RuntimeError, match="closed"):
        support.set_signature(b"sig")


def test_close_is_idempotent() -> None:
    """Calling :meth:`close` twice is a no-op — the second call drops
    the already-``None`` reference without raising."""
    writer = _FakeCOSWriter(b"data")
    support = SigningSupport(writer)  # type: ignore[arg-type]
    support.close()
    # Second close — must not raise.
    support.close()


def test_context_manager_enter_returns_self() -> None:
    """``__enter__`` returns the same instance the user constructed."""
    writer = _FakeCOSWriter(b"")
    support = SigningSupport(writer)  # type: ignore[arg-type]
    assert support.__enter__() is support
    # Clean up after the manual __enter__ since we didn't go through ``with``.
    support.close()


def test_get_content_then_set_signature_pair_round_trip() -> None:
    """Realistic flow — pull the data-to-sign, pretend to sign, push the
    signature back. Confirms both halves cooperate with the same backing
    COSWriter."""
    writer = _FakeCOSWriter(b"document-bytes")
    with SigningSupport(writer) as support:  # type: ignore[arg-type]
        body = support.get_content().read()
        # "Sign" by hashing — pretend it's a CMS blob.
        import hashlib

        sig = hashlib.sha256(body).digest()
        support.set_signature(sig)
    assert writer.installed_signature is not None
    assert writer.installed_signature == hashlib.sha256(b"document-bytes").digest()
