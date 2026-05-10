"""Upstream-style parity tests for ``SecurityHandler`` base helpers.

PDFBox does not ship a dedicated ``SecurityHandlerTest`` JUnit class — the
base is exercised indirectly through ``StandardSecurityHandler`` and
``PublicKeySecurityHandler`` upstream. To meet the wave's parity-tests
requirement we hand-port a focused set of behavioural assertions that
mirror the public surface introduced in this wave (filter names, secure
random override, version-number computation, COSBase decrypt dispatch,
RC4 / AES-256 byte helpers, AES IV preparation).
"""

from __future__ import annotations

import io

import pytest

from pypdfbox.cos.cos_array import COSArray
from pypdfbox.cos.cos_dictionary import COSDictionary
from pypdfbox.cos.cos_name import COSName
from pypdfbox.cos.cos_string import COSString
from pypdfbox.pdmodel.encryption.security_handler import SecurityHandler


class _BareHandler(SecurityHandler):
    def prepare_for_decryption(
        self,
        encryption: object,
        document_id: bytes,
        decryption_material: object,
    ) -> None:  # pragma: no cover — not exercised here
        pass

    def prepare_document(self, document: object) -> None:  # pragma: no cover
        pass


def _rc4_handler(key: bytes = b"K" * 5) -> _BareHandler:
    h = _BareHandler()
    h.set_encryption_key(key)
    h.set_revision(2)
    h.set_aes(False)
    return h


# ----------------------------------------------------- filter-name accessors


def test_string_filter_name_round_trip() -> None:
    h = _BareHandler()
    assert h.get_string_filter_name() is None
    h.set_string_filter_name("V2")
    assert h.get_string_filter_name() == "V2"


def test_stream_filter_name_round_trip() -> None:
    h = _BareHandler()
    assert h.get_stream_filter_name() is None
    h.set_stream_filter_name("AESV3")
    assert h.get_stream_filter_name() == "AESV3"


# ------------------------------------------------------- protection policy


def test_protection_policy_default_absent() -> None:
    h = _BareHandler()
    assert h.has_protection_policy() is False
    assert h.get_protection_policy() is None


def test_protection_policy_round_trip() -> None:
    h = _BareHandler()
    sentinel = object()
    h.set_protection_policy(sentinel)
    assert h.has_protection_policy() is True
    assert h.get_protection_policy() is sentinel


# ----------------------------------------------------- compute_version_number


def test_compute_version_number_40() -> None:
    h = _BareHandler()
    h.set_key_length(40)
    assert h.compute_version_number() == 1


def test_compute_version_number_128_no_aes() -> None:
    h = _BareHandler()
    h.set_key_length(128)
    assert h.compute_version_number() == 2


def test_compute_version_number_128_prefer_aes() -> None:
    class _Policy:
        def is_prefer_aes(self) -> bool:
            return True

    h = _BareHandler()
    h.set_key_length(128)
    h.set_protection_policy(_Policy())
    assert h.compute_version_number() == 4


def test_compute_version_number_256() -> None:
    h = _BareHandler()
    h.set_key_length(256)
    assert h.compute_version_number() == 5


# ---------------------------------------------------------- secure random


def test_default_secure_random_returns_bytes() -> None:
    h = _BareHandler()
    rng = h.get_secure_random()
    out = rng.read(16)
    assert isinstance(out, bytes)
    assert len(out) == 16


def test_set_custom_secure_random_overrides_default() -> None:
    fixed = bytes(range(16))

    class _Stub:
        def read(self, n: int) -> bytes:
            return fixed[:n]

    h = _BareHandler()
    stub = _Stub()
    h.set_custom_secure_random(stub)
    assert h.get_secure_random() is stub


# ---------------------------------------------------- AES IV preparation


def test_prepare_aes_iv_decrypt_reads_16_bytes() -> None:
    h = _BareHandler()
    src = io.BytesIO(bytes(range(16)) + b"ciphertext")
    iv = bytearray(16)
    ok = h.prepare_aes_initialization_vector(True, iv, src, None)
    assert ok is True
    assert bytes(iv) == bytes(range(16))
    # Subsequent reads start at the ciphertext, IV consumed in place.
    assert src.read() == b"ciphertext"


def test_prepare_aes_iv_decrypt_empty_returns_false() -> None:
    h = _BareHandler()
    iv = bytearray(16)
    assert h.prepare_aes_initialization_vector(True, iv, io.BytesIO(b""), None) is False


def test_prepare_aes_iv_decrypt_short_raises() -> None:
    h = _BareHandler()
    iv = bytearray(16)
    with pytest.raises(OSError):
        h.prepare_aes_initialization_vector(True, iv, io.BytesIO(b"too short"), None)


def test_prepare_aes_iv_encrypt_writes_iv_to_output() -> None:
    h = _BareHandler()
    iv = bytearray(16)
    sink = io.BytesIO()
    ok = h.prepare_aes_initialization_vector(False, iv, io.BytesIO(b""), sink)
    assert ok is True
    written = sink.getvalue()
    assert len(written) == 16
    assert bytes(iv) == written


# ---------------------------------------------------------- create_cipher


def test_create_cipher_round_trip() -> None:
    from cryptography.hazmat.primitives import padding

    h = _BareHandler()
    key = b"A" * 16
    iv = b"B" * 16
    enc = h.create_cipher(key, iv, decrypt=False).encryptor()
    dec = h.create_cipher(key, iv, decrypt=True).decryptor()
    pad = padding.PKCS7(128).padder()
    unpad = padding.PKCS7(128).unpadder()
    plain = b"hello world"
    padded = pad.update(plain) + pad.finalize()
    ciphertext = enc.update(padded) + enc.finalize()
    decoded = dec.update(ciphertext) + dec.finalize()
    assert unpad.update(decoded) + unpad.finalize() == plain


# ----------------------------------------------------------- RC4 helper


def test_encrypt_data_rc4_bytes_round_trip() -> None:
    h = _BareHandler()
    key = b"\x01\x02\x03\x04\x05"
    enc = h.encrypt_data_rc4(key, b"hello")
    # RC4 is symmetric — encrypt twice with same key returns plaintext.
    assert h.encrypt_data_rc4(key, enc) == b"hello"


def test_encrypt_data_rc4_writes_to_output() -> None:
    h = _BareHandler()
    sink = io.BytesIO()
    out = h.encrypt_data_rc4(b"\x01" * 5, b"abc", output=sink)
    assert sink.getvalue() == out


def test_encrypt_data_rc4_accepts_stream_input() -> None:
    h = _BareHandler()
    src = io.BytesIO(b"plain")
    enc = h.encrypt_data_rc4(b"\x01" * 5, src)
    assert h.encrypt_data_rc4(b"\x01" * 5, enc) == b"plain"


# --------------------------------------------------------- AES-256 helper


def test_encrypt_data_aes256_round_trip() -> None:
    h = _BareHandler()
    h.set_encryption_key(b"K" * 32)
    payload = b"the quick brown fox"
    ct = h.encrypt_data_aes256(payload)
    pt = h.encrypt_data_aes256(ct, decrypt=True)
    assert pt == payload


def test_encrypt_data_aes256_requires_key() -> None:
    h = _BareHandler()
    with pytest.raises(ValueError):
        h.encrypt_data_aes256(b"x" * 16)


# --------------------------------------------------- COSBase decrypt dispatch


def test_decrypt_passthrough_for_non_cos() -> None:
    h = _rc4_handler()
    assert h.decrypt(123, 1, 0) == 123  # type: ignore[arg-type]
    assert h.decrypt("abc", 1, 0) == "abc"  # type: ignore[arg-type]


def test_decrypt_string_in_place_via_dispatch() -> None:
    h = _rc4_handler()
    plain = b"target"
    cs = COSString(h.encrypt_string(plain, 1, 0))
    h.decrypt(cs, 1, 0)
    assert cs.get_bytes() == plain


def test_decrypt_string_idempotent_within_same_handler() -> None:
    """Mirrors PDFBOX-4477: a string in the IdentityHashMap is skipped."""
    h = _rc4_handler()
    plain = b"target"
    cs = COSString(h.encrypt_string(plain, 1, 0))
    h.decrypt(cs, 1, 0)
    assert cs.get_bytes() == plain
    # Second call must not double-decrypt (which would corrupt the string).
    h.decrypt(cs, 1, 0)
    assert cs.get_bytes() == plain


def test_decrypt_string_identity_filter_skipped() -> None:
    h = _rc4_handler()
    h.set_string_filter_name(COSName.get_pdf_name("Identity"))
    cs = COSString(b"already-plain")
    h.decrypt(cs, 1, 0)
    assert cs.get_bytes() == b"already-plain"


def test_decrypt_array_walks_elements() -> None:
    h = _rc4_handler()
    arr = COSArray()
    arr.add(COSString(h.encrypt_string(b"a", 9, 0)))
    arr.add(COSString(h.encrypt_string(b"bb", 9, 0)))
    h.decrypt(arr, 9, 0)
    assert arr[0].get_bytes() == b"a"  # type: ignore[union-attr]
    assert arr[1].get_bytes() == b"bb"  # type: ignore[union-attr]


def test_decrypt_dictionary_skips_cf_dict() -> None:
    """PDFBOX-2936: a dict carrying /CF is left untouched by decrypt()."""
    h = _rc4_handler()
    d = COSDictionary()
    d.set_item(COSName.get_pdf_name("CF"), COSDictionary())
    inner_cs = COSString(b"would-be-ciphertext")
    d.set_item(COSName.get_pdf_name("Foo"), inner_cs)
    h.decrypt(d, 1, 0)
    # The /Foo string must remain byte-identical (no decryption attempt).
    assert inner_cs.get_bytes() == b"would-be-ciphertext"


# ---------------------------------------------------- prepare_document_for_encryption


def test_prepare_document_for_encryption_delegates_to_prepare_document() -> None:
    calls: list[object] = []

    class _Recording(_BareHandler):
        def prepare_document(self, document: object) -> None:
            calls.append(document)

    sentinel = object()
    _Recording().prepare_document_for_encryption(sentinel)
    assert calls == [sentinel]


# --------------------------------------------------------------- calc_final_key


def test_calc_final_key_alias_matches_compute_object_key() -> None:
    h = _BareHandler()
    h.set_encryption_key(b"K" * 16)
    h.set_revision(4)
    assert h.calc_final_key(7, 0) == h.compute_object_key(7, 0)
