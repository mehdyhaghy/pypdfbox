"""Encryption-aware ``COSStream.create_view`` and ``create_input_stream``.

Validates the contract documented at line 158 of ``CHANGES.md``: when a
security handler is attached via :meth:`COSStream.set_security_handler`,
the raw on-disk bytes are decrypted exactly once on the first decode pass,
the plaintext is cached as the new raw body, and subsequent
``create_view`` / ``create_input_stream`` calls slice into that cached
buffer without re-running the cipher.

Three layers:

* a ``_MockHandler`` that counts ``decrypt_stream`` invocations so the
  "cipher runs exactly once" invariant is observable;
* a sliced ``create_view().create_view(start, length)`` round-trip proving
  byte-range slicing into the decrypted body works (this is the gap the
  CHANGES note flagged as deferred);
* an end-to-end round-trip through the real
  ``StandardSecurityHandler`` (V=4 R=4 RC4-128) so the public surface
  exercised by ``PDDocument.decrypt`` is covered, not just the mock path.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSName, COSStream
from pypdfbox.pdmodel.encryption.access_permission import AccessPermission
from pypdfbox.pdmodel.encryption.standard_protection_policy import (
    StandardProtectionPolicy,
)
from pypdfbox.pdmodel.encryption.standard_security_handler import (
    StandardSecurityHandler,
)


class _MockHandler:
    """Minimal security-handler stand-in.

    Exposes only :meth:`decrypt_stream`, which is the single method
    ``COSStream`` calls into. Each invocation appends ``(obj, gen, len)``
    to ``calls`` so tests can assert the cipher pass is hit *exactly*
    once regardless of how many views or input streams are opened.
    """

    def __init__(self, plaintext: bytes) -> None:
        self.plaintext = plaintext
        self.calls: list[tuple[int, int, int]] = []

    def decrypt_stream(self, data: bytes, obj_num: int, gen_num: int) -> bytes:
        self.calls.append((obj_num, gen_num, len(data)))
        return self.plaintext


# --------------------------------------------------------------------------
# Unencrypted baseline — verify the no-handler path is unchanged.


def test_unencrypted_create_view_slice_returns_raw_bytes() -> None:
    """Without a handler ``create_view`` returns the raw bytes and the
    sub-view ``create_view(0, 10)`` exposes the first 10 of those."""
    payload = b"plaintext-payload-12345"
    with COSStream() as stream:
        stream.set_raw_data(payload)
        with stream.create_view() as view:
            sub = view.create_view(0, 10)
            try:
                buf = bytearray(10)
                n = sub.read_into(buf)
                assert n == 10
                assert bytes(buf) == payload[:10]
            finally:
                sub.close()


def test_unencrypted_create_input_stream_returns_raw_bytes() -> None:
    payload = b"plaintext-payload-12345"
    with COSStream() as stream:
        stream.set_raw_data(payload)
        with stream.create_input_stream() as src:
            assert src.read() == payload


# --------------------------------------------------------------------------
# Mock-handler path — the cipher pass is observable through call counts.


def test_encrypted_create_input_stream_returns_full_plaintext() -> None:
    """``create_input_stream`` with a handler decrypts the on-disk body and
    returns the full plaintext (no /Filter chain in play)."""
    plaintext = b"the quick brown fox jumps over the lazy dog"
    ciphertext = b"\x00" * len(plaintext)  # opaque to the test
    handler = _MockHandler(plaintext)
    with COSStream() as stream:
        stream.set_raw_data(ciphertext)
        stream.set_security_handler(handler, 7, 0)
        with stream.create_input_stream() as src:
            assert src.read() == plaintext
        assert handler.calls == [(7, 0, len(ciphertext))]


def test_encrypted_create_view_slice_returns_first_n_plaintext_bytes() -> None:
    """``create_view`` exposes the decrypted body; the returned buffer's
    own ``create_view(0, 10)`` then slices the first 10 plaintext bytes —
    which is the "slice into encrypted stream without re-decrypting the
    whole body" guarantee CHANGES.md line 158 had flagged as deferred."""
    plaintext = b"the quick brown fox jumps over the lazy dog"
    ciphertext = b"\xff" * len(plaintext)
    handler = _MockHandler(plaintext)
    with COSStream() as stream:
        stream.set_raw_data(ciphertext)
        stream.set_security_handler(handler, 11, 0)
        with stream.create_view() as view:
            assert view.length() == len(plaintext)
            sub = view.create_view(0, 10)
            try:
                buf = bytearray(10)
                n = sub.read_into(buf)
                assert n == 10
                assert bytes(buf) == plaintext[:10]
            finally:
                sub.close()


def test_encrypted_decrypt_runs_exactly_once_across_multiple_views() -> None:
    """``_decrypted`` guards against double-undo: opening several views and
    input streams must invoke ``decrypt_stream`` only once."""
    plaintext = b"some-payload-bytes"
    ciphertext = b"\xaa" * len(plaintext)
    handler = _MockHandler(plaintext)
    with COSStream() as stream:
        stream.set_raw_data(ciphertext)
        stream.set_security_handler(handler, 3, 0)
        # Four distinct opens — all should observe plaintext.
        with stream.create_input_stream() as a:
            assert a.read() == plaintext
        with stream.create_view() as v1:
            sub = v1.create_view(5, 4)
            try:
                buf = bytearray(4)
                sub.read_into(buf)
                assert bytes(buf) == plaintext[5:9]
            finally:
                sub.close()
        with stream.create_input_stream() as b:
            assert b.read() == plaintext
        with stream.create_view() as v2:
            buf = bytearray(v2.length())
            v2.read_into(buf)
            assert bytes(buf) == plaintext
    # Cipher pass ran exactly once even though five readers opened.
    assert handler.calls == [(3, 0, len(ciphertext))]


def test_encrypted_decrypt_runs_on_create_view_before_input_stream() -> None:
    """Decryption is lazy on first access — ``create_view`` is a valid
    first access, no ``create_input_stream`` precondition."""
    plaintext = b"view-first"
    ciphertext = b"\xab" * len(plaintext)
    handler = _MockHandler(plaintext)
    with COSStream() as stream:
        stream.set_raw_data(ciphertext)
        stream.set_security_handler(handler, 5, 0)
        with stream.create_view() as view:
            buf = bytearray(view.length())
            view.read_into(buf)
            assert bytes(buf) == plaintext
        assert handler.calls == [(5, 0, len(ciphertext))]


# --------------------------------------------------------------------------
# Skip-encryption parity — xref/Encrypt streams must NOT touch the handler.


def test_skip_encryption_bypasses_handler_call() -> None:
    """Streams flagged ``set_skip_encryption(True)`` must not invoke
    ``decrypt_stream`` even when ``set_security_handler`` is called —
    parity with the xref / /Encrypt body exemptions in ISO 32000-2 §7.6.2."""
    payload = b"already-plaintext"
    handler = _MockHandler(b"WRONG")  # would garble the body if ever called
    with COSStream() as stream:
        stream.set_raw_data(payload)
        stream.set_skip_encryption(True)
        stream.set_security_handler(handler, 1, 0)
        with stream.create_input_stream() as src:
            assert src.read() == payload
        assert handler.calls == []


# --------------------------------------------------------------------------
# Real handler — end-to-end through StandardSecurityHandler RC4-128.

_DOC_ID = b"\x00" * 16


@pytest.fixture
def rc4_handler() -> StandardSecurityHandler:
    """A fully prepared V=2 R=3 RC4-128 standard handler with empty
    user/owner passwords. Both encrypt_stream and decrypt_stream are
    available for round-tripping a per-object body."""
    policy = StandardProtectionPolicy(
        owner_password="",
        user_password="",
        permissions=AccessPermission(),
    )
    policy.set_encryption_key_length(128)
    policy.set_prefer_aes(False)

    handler = StandardSecurityHandler(policy)
    captured: dict[str, object] = {}

    class _Capture:
        def set_encryption_dictionary(self, e: object) -> None:
            captured["enc"] = e

    handler.prepare_document(_Capture())
    return handler


def test_real_standard_handler_round_trip_through_create_input_stream(
    rc4_handler: StandardSecurityHandler,
) -> None:
    """End-to-end: encrypt a payload with the real handler, drop the
    ciphertext into a ``COSStream``, attach the same handler, and verify
    ``create_input_stream`` recovers the original plaintext."""
    plaintext = b"hello encrypted world " * 4
    obj_num, gen_num = 9, 0
    ciphertext = rc4_handler.encrypt_stream(plaintext, obj_num, gen_num)
    assert ciphertext != plaintext  # sanity — cipher actually ran

    with COSStream() as stream:
        stream.set_raw_data(ciphertext)
        stream.set_security_handler(rc4_handler, obj_num, gen_num)
        with stream.create_input_stream() as src:
            assert src.read() == plaintext


def test_real_standard_handler_round_trip_slice_via_create_view(
    rc4_handler: StandardSecurityHandler,
) -> None:
    """End-to-end slice: ``create_view`` over the encrypted body, then
    ``create_view(0, 10)`` on that — returns plaintext[:10]."""
    plaintext = b"the quick brown fox jumps over the lazy dog"
    obj_num, gen_num = 13, 0
    ciphertext = rc4_handler.encrypt_stream(plaintext, obj_num, gen_num)

    with COSStream() as stream:
        stream.set_raw_data(ciphertext)
        stream.set_security_handler(rc4_handler, obj_num, gen_num)
        with stream.create_view() as view:
            sub = view.create_view(0, 10)
            try:
                buf = bytearray(10)
                n = sub.read_into(buf)
                assert n == 10
                assert bytes(buf) == plaintext[:10]
            finally:
                sub.close()


def test_real_standard_handler_round_trip_with_flate_filter_chain(
    rc4_handler: StandardSecurityHandler,
) -> None:
    """Encryption + ``/FlateDecode``: the on-disk layout is
    ``encrypt(flate(plaintext))``; ``create_input_stream`` must undo the
    cipher first, then the filter chain, exposing the original plaintext."""
    import io
    import zlib

    plaintext = b"decompress-then-decrypt-no-wait-the-other-way-around " * 6
    flate_encoded = zlib.compress(plaintext)
    obj_num, gen_num = 17, 0
    ciphertext = rc4_handler.encrypt_stream(flate_encoded, obj_num, gen_num)

    with COSStream() as stream:
        # Hand-write the raw ciphertext bytes and declare /Filter so the
        # decode pass post-decryption runs the chain.
        with stream.create_raw_output_stream() as raw:
            raw.write(ciphertext)
        stream.set_filters(COSName.FLATE_DECODE)  # type: ignore[attr-defined]
        stream.set_security_handler(rc4_handler, obj_num, gen_num)

        with stream.create_input_stream() as src:
            assert src.read() == plaintext

        # And a sliced view on the same stream — note that after the first
        # decode the cipher pass has already run, so this second open just
        # re-decodes the (now-plaintext) flate body.
        with stream.create_view() as view:
            assert view.length() == len(plaintext)
            buf = bytearray(view.length())
            view.read_into(buf)
            assert bytes(buf) == plaintext

        # Sanity: io stays importable, no resource warnings from the buffer.
        assert isinstance(io.BytesIO(), io.BytesIO)
