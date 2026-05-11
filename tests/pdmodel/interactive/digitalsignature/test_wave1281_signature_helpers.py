"""Wave 1281 — parity ports for SignatureOptions / SigningSupport."""

from __future__ import annotations

import io

import pytest

from pypdfbox.pdmodel.interactive.digitalsignature.signature_options import (
    DEFAULT_SIGNATURE_SIZE,
    SignatureOptions,
)
from pypdfbox.pdmodel.interactive.digitalsignature.signing_support import (
    SigningSupport,
)


class TestSignatureOptions:
    def test_default_page_zero(self) -> None:
        opts = SignatureOptions()
        assert opts.get_page() == 0

    def test_set_then_get_page(self) -> None:
        opts = SignatureOptions()
        opts.set_page(3)
        assert opts.get_page() == 3

    def test_default_signature_size_constant(self) -> None:
        assert SignatureOptions.DEFAULT_SIGNATURE_SIZE == 0x2500
        assert DEFAULT_SIGNATURE_SIZE == 0x2500

    def test_preferred_signature_size_starts_zero(self) -> None:
        opts = SignatureOptions()
        assert opts.get_preferred_signature_size() == 0

    def test_set_preferred_size_positive(self) -> None:
        opts = SignatureOptions()
        opts.set_preferred_signature_size(1024)
        assert opts.get_preferred_signature_size() == 1024

    def test_set_preferred_size_ignores_non_positive(self) -> None:
        opts = SignatureOptions()
        opts.set_preferred_signature_size(0)
        opts.set_preferred_signature_size(-3)
        assert opts.get_preferred_signature_size() == 0

    def test_visual_signature_starts_none(self) -> None:
        opts = SignatureOptions()
        assert opts.get_visual_signature() is None

    def test_close_is_idempotent(self) -> None:
        opts = SignatureOptions()
        opts.close()
        opts.close()  # second close must not raise

    def test_context_manager_closes(self) -> None:
        with SignatureOptions() as opts:
            opts.set_page(2)
            assert opts.get_page() == 2


class _StubWriter:
    """Stand-in for COSWriter — records signature bytes."""

    def __init__(self) -> None:
        self.signature: bytes | None = None
        self._content = io.BytesIO(b"unsigned-bytes")

    def get_data_to_sign(self) -> io.BytesIO:
        return self._content

    def write_external_signature(self, signature: bytes) -> None:
        self.signature = signature


class TestSigningSupport:
    def test_get_content_returns_writer_payload(self) -> None:
        writer = _StubWriter()
        support = SigningSupport(writer)
        stream = support.get_content()
        assert stream.read() == b"unsigned-bytes"

    def test_set_signature_forwards_to_writer(self) -> None:
        writer = _StubWriter()
        support = SigningSupport(writer)
        support.set_signature(b"signed!")
        assert writer.signature == b"signed!"

    def test_close_disconnects_writer(self) -> None:
        writer = _StubWriter()
        support = SigningSupport(writer)
        support.close()
        with pytest.raises(RuntimeError):
            support.get_content()
        with pytest.raises(RuntimeError):
            support.set_signature(b"x")

    def test_context_manager(self) -> None:
        writer = _StubWriter()
        with SigningSupport(writer) as support:
            support.set_signature(b"x")
        assert writer.signature == b"x"
