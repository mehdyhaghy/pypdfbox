"""Wave 1573 fuzz/parity battery for the AES crypt-filter primitives.

Hammers the AES-CBC string/stream cipher surface of ``SecurityHandler`` /
``StandardSecurityHandler`` against upstream PDFBox 3.0.7 semantics
(``SecurityHandler.encryptData`` / ``decryptData`` / ``calculateObjectKey`` /
``prepareAESInitializationVector`` / ``encryptDataAESother`` /
``encryptDataAES256``):

* AESV2 (128-bit, /V4, per-object key) encrypt -> decrypt round-trip across
  plaintext lengths that straddle the 16-byte block boundary (0, 1, 15, 16,
  17, 31, 32 ...) — exercising PKCS#5/7 padding at and across block edges.
* The 16-byte random IV is *prepended* to the ciphertext; decrypt strips the
  IV then unpads. Two independent encryptions of the same plaintext differ
  (fresh IV) yet both decrypt back.
* AESV3 (256-bit, /V5/R6) round-trip uses the document key directly — no
  per-object salt — selected by ``useAES && key.length == 32``.
* AESV2 per-object key derivation: ``MD5(file_key || obj[0:3] LE ||
  gen[0:2] LE || "sAlT")`` truncated to ``min(n+5, 16)`` bytes; the salt is
  present for AESV2 and absent for RC4; AESV3 (R>=5) returns the file key
  verbatim.
* Empty plaintext still produces a full 16-byte padding block (one cipher
  block of ciphertext after the IV).
* Corrupted / short ciphertext: partial IV raises, IV-only yields empty, a
  bad final block raises for AESV2 (Cipher.update+doFinal) but is tolerated
  for AESV3 (CipherInputStream).
* The /Identity crypt-filter is a pure pass-through.
"""

from __future__ import annotations

import hashlib

import pytest

from pypdfbox.cos import COSArray, COSString
from pypdfbox.pdmodel.encryption.access_permission import AccessPermission
from pypdfbox.pdmodel.encryption.pd_encryption import PDEncryption
from pypdfbox.pdmodel.encryption.security_handler import (
    _AES_SALT,
    _aes_cbc_decrypt,
    _aes_cbc_encrypt,
)
from pypdfbox.pdmodel.encryption.standard_protection_policy import (
    StandardProtectionPolicy,
)
from pypdfbox.pdmodel.encryption.standard_security_handler import (
    StandardDecryptionMaterial,
    StandardSecurityHandler,
    _aes128_cbc_decrypt,
    _aes128_cbc_encrypt,
)

# Plaintext lengths that straddle the AES block (16-byte) boundary.
_BLOCK_EDGE_LENGTHS = [0, 1, 15, 16, 17, 31, 32, 33, 47, 48, 64, 100, 255]

# ---------------------------------------------------------------------------
# A minimal handler with a fixed file key so the AES dispatch can be exercised
# without a full prepare_for_decryption round.
# ---------------------------------------------------------------------------


def _handler_with_key(key: bytes, *, aes: bool, revision: int) -> StandardSecurityHandler:
    h = StandardSecurityHandler()
    h.set_encryption_key(key)
    h.set_aes(aes)
    h.set_revision(revision)
    h.set_key_length(len(key) * 8)
    return h


# ===========================================================================
# 1. Raw AES-CBC helper round-trip across block boundaries (AESV2 key length).
# ===========================================================================


@pytest.mark.parametrize("length", _BLOCK_EDGE_LENGTHS)
def test_aes128_helper_roundtrip(length: int) -> None:
    key = bytes(range(16))
    plain = bytes((i * 7 + 3) & 0xFF for i in range(length))
    blob = _aes128_cbc_encrypt(key, plain)
    assert _aes128_cbc_decrypt(key, blob) == plain


@pytest.mark.parametrize("length", _BLOCK_EDGE_LENGTHS)
def test_security_handler_helper_roundtrip(length: int) -> None:
    key = bytes(range(16))
    plain = bytes((i * 11 + 1) & 0xFF for i in range(length))
    blob = _aes_cbc_encrypt(key, plain)
    assert _aes_cbc_decrypt(key, blob, tolerant_padding=False) == plain


# ===========================================================================
# 2. IV is 16 random bytes prepended; ciphertext layout + freshness.
# ===========================================================================


def test_iv_is_prepended_16_bytes() -> None:
    key = bytes(range(16))
    plain = b"hello world, exactly some bytes"
    blob = _aes128_cbc_encrypt(key, plain)
    # IV (16) + at least one PKCS#7 block of ciphertext.
    assert len(blob) >= 32
    assert (len(blob) - 16) % 16 == 0


def test_two_encryptions_differ_but_both_decrypt() -> None:
    key = bytes(range(16))
    plain = b"same plaintext"
    a = _aes128_cbc_encrypt(key, plain)
    b = _aes128_cbc_encrypt(key, plain)
    # Fresh random IV each time -> different blobs, different IV prefix.
    assert a != b
    assert a[:16] != b[:16]
    assert _aes128_cbc_decrypt(key, a) == plain
    assert _aes128_cbc_decrypt(key, b) == plain


def test_empty_plaintext_emits_full_padding_block() -> None:
    key = bytes(range(16))
    blob = _aes128_cbc_encrypt(key, b"")
    # IV (16) + exactly one block (16) of pure PKCS#7 padding (0x10 * 16).
    assert len(blob) == 32
    assert _aes128_cbc_decrypt(key, blob) == b""


# ===========================================================================
# 3. AESV3 256-bit round-trip uses the file key directly (no per-object salt).
# ===========================================================================


@pytest.mark.parametrize("length", _BLOCK_EDGE_LENGTHS)
def test_aes256_helper_roundtrip(length: int) -> None:
    key = bytes(range(32))
    plain = bytes((i * 5 + 9) & 0xFF for i in range(length))
    blob = _aes128_cbc_encrypt(key, plain)
    assert _aes128_cbc_decrypt(key, blob) == plain


def test_aes256_uses_document_key_no_object_key() -> None:
    key = bytes(range(32))
    h = _handler_with_key(key, aes=True, revision=6)
    # For R>=5 compute_object_key returns the file key verbatim for any obj/gen.
    assert h.compute_object_key(7, 0) == key
    assert h.compute_object_key(99999, 65535) == key


def test_aes256_dispatch_roundtrip_via_handler() -> None:
    key = bytes(range(32))
    h = _handler_with_key(key, aes=True, revision=6)
    plain = b"AES-256 stream payload that crosses two blocks!!"
    blob = h.encrypt_stream(plain, 12, 0)
    assert h.decrypt_stream(blob, 12, 0) == plain


# ===========================================================================
# 4. AESV2 per-object key derivation parity with calculateObjectKey.
# ===========================================================================


def _expected_object_key(
    file_key: bytes, obj_num: int, gen_num: int, *, aes: bool
) -> bytes:
    md5 = hashlib.md5(usedforsecurity=False)
    md5.update(file_key)
    md5.update(
        bytes(
            [
                obj_num & 0xFF,
                (obj_num >> 8) & 0xFF,
                (obj_num >> 16) & 0xFF,
                gen_num & 0xFF,
                (gen_num >> 8) & 0xFF,
            ]
        )
    )
    if aes:
        md5.update(b"sAlT")
    n = len(file_key)
    return md5.digest()[: min(n + 5, 16)]


@pytest.mark.parametrize(
    ("obj_num", "gen_num"),
    [(1, 0), (7, 0), (255, 0), (256, 1), (0x010203, 0x0405), (0xFFFFFF, 0xFFFF)],
)
def test_object_key_aesv2_matches_spec(obj_num: int, gen_num: int) -> None:
    file_key = bytes(range(16))
    h = _handler_with_key(file_key, aes=True, revision=4)
    got = h.compute_object_key(obj_num, gen_num, aes=True)
    assert got == _expected_object_key(file_key, obj_num, gen_num, aes=True)


def test_object_key_salt_is_lowercase_s_capital_a_l_capital_t() -> None:
    # Guard the exact "sAlT" bytes — a wrong-case salt silently breaks parity.
    assert _AES_SALT == b"sAlT"


def test_object_key_rc4_omits_salt() -> None:
    file_key = bytes(range(16))
    h = _handler_with_key(file_key, aes=False, revision=4)
    got = h.compute_object_key(5, 0, aes=False)
    assert got == _expected_object_key(file_key, 5, 0, aes=False)
    # AES and RC4 derivations must differ (the salt is the only difference).
    assert got != _expected_object_key(file_key, 5, 0, aes=True)


@pytest.mark.parametrize("key_bytes", [5, 16])
def test_object_key_length_cap_min_n_plus_5_16(key_bytes: int) -> None:
    file_key = bytes(range(key_bytes))
    h = _handler_with_key(file_key, aes=True, revision=4)
    got = h.compute_object_key(1, 0, aes=True)
    assert len(got) == min(key_bytes + 5, 16)


def test_object_key_byte_order_is_little_endian() -> None:
    # obj 0x010203 -> low bytes 03,02,01 ; gen 0x0405 -> 05,04.
    file_key = b"K" * 16
    h = _handler_with_key(file_key, aes=True, revision=4)
    md5 = hashlib.md5(usedforsecurity=False)
    md5.update(file_key)
    md5.update(bytes([0x03, 0x02, 0x01, 0x05, 0x04]))
    md5.update(b"sAlT")
    expected = md5.digest()[:16]
    assert h.compute_object_key(0x010203, 0x0405, aes=True) == expected


# ===========================================================================
# 5. AESV2 per-object dispatch round-trip through the handler.
# ===========================================================================


@pytest.mark.parametrize("length", [0, 1, 15, 16, 17, 32])
def test_aesv2_handler_roundtrip(length: int) -> None:
    file_key = bytes(range(16))
    h = _handler_with_key(file_key, aes=True, revision=4)
    plain = bytes((i + 1) & 0xFF for i in range(length))
    blob = h.encrypt_string(plain, 42, 0)
    assert h.decrypt_string(blob, 42, 0) == plain


def test_aesv2_wrong_object_number_fails_to_decrypt() -> None:
    file_key = bytes(range(16))
    h = _handler_with_key(file_key, aes=True, revision=4)
    plain = b"object-scoped secret"
    blob = h.encrypt_string(plain, 10, 0)
    # Decrypting with a different obj_num uses a different per-object key, so
    # either the bytes mismatch or padding validation raises (AESV2 = strict).
    try:
        out = h.decrypt_string(blob, 11, 0)
    except OSError:
        return
    assert out != plain


# ===========================================================================
# 6. Corrupted / short ciphertext handling.
# ===========================================================================


def test_empty_input_yields_empty() -> None:
    key = bytes(range(16))
    assert _aes128_cbc_decrypt(key, b"") == b""
    assert _aes_cbc_decrypt(key, b"", tolerant_padding=False) == b""


@pytest.mark.parametrize("partial_len", [1, 5, 15])
def test_partial_iv_raises(partial_len: int) -> None:
    key = bytes(range(16))
    with pytest.raises(OSError, match="initialization vector"):
        _aes128_cbc_decrypt(key, b"\x00" * partial_len)
    with pytest.raises(OSError, match="initialization vector"):
        _aes_cbc_decrypt(key, b"\x00" * partial_len, tolerant_padding=False)


def test_iv_only_no_ciphertext_yields_empty() -> None:
    key = bytes(range(16))
    assert _aes128_cbc_decrypt(key, b"\x00" * 16) == b""


def test_aesv2_bad_final_block_raises() -> None:
    # 16-byte key -> strict (encryptDataAESother): bad padding raises OSError.
    key = bytes(range(16))
    iv = b"\x00" * 16
    bogus_ct = b"\xff" * 16  # decrypts to garbage -> invalid PKCS#7.
    with pytest.raises(OSError):
        _aes128_cbc_decrypt(key, iv + bogus_ct)


def test_aesv2_non_block_multiple_raises() -> None:
    key = bytes(range(16))
    iv = b"\x00" * 16
    with pytest.raises(OSError, match="multiple of the block size"):
        _aes128_cbc_decrypt(key, iv + b"\x01" * 7)


def test_aes256_tolerant_drops_bad_final_block() -> None:
    # 32-byte key -> tolerant (encryptDataAES256 / CipherInputStream): a bad
    # final block is silently dropped rather than raising.
    key = bytes(range(32))
    iv = b"\x00" * 16
    bogus_ct = b"\xff" * 16
    # Should not raise; tolerant path returns leading clean blocks (here none).
    out = _aes128_cbc_decrypt(key, iv + bogus_ct)
    assert isinstance(out, bytes)


def test_aes256_tolerant_non_block_multiple_no_raise() -> None:
    key = bytes(range(32))
    iv = b"\x00" * 16
    out = _aes128_cbc_decrypt(key, iv + b"\x01" * 7)
    assert isinstance(out, bytes)


# ===========================================================================
# 7. /Identity crypt-filter pass-through.
# ===========================================================================


def _identity_handler() -> StandardSecurityHandler:
    h = StandardSecurityHandler()
    h.set_encryption_key(bytes(range(16)))
    h.set_aes(True)
    h.set_revision(4)
    # Force the per-object dispatch to the /Identity branch.
    h._stream_cfm = "Identity"
    h._string_cfm = "Identity"
    return h


@pytest.mark.parametrize("payload", [b"", b"x", b"\x00\x01\x02", b"A" * 100])
def test_identity_stream_passthrough(payload: bytes) -> None:
    h = _identity_handler()
    assert h.encrypt_stream(payload, 1, 0) == payload
    assert h.decrypt_stream(payload, 1, 0) == payload


def test_identity_dispatch_returns_input_unchanged() -> None:
    h = StandardSecurityHandler()
    h.set_encryption_key(bytes(range(16)))
    data = b"unencrypted bytes stay as-is"
    assert h._dispatch_decrypt("Identity", data, 3, 0) == data
    assert h._dispatch_encrypt("Identity", data, 3, 0) == data


# ===========================================================================
# 8. Full standard-handler AESV2 / AESV3 reload round-trip (end-to-end).
# ===========================================================================


class _FakeDoc:
    def __init__(self) -> None:
        self._id = b"\x01" * 16
        self.encryption: PDEncryption | None = None

    def get_document_id(self) -> COSArray:
        arr = COSArray()
        arr.add(COSString(self._id))
        return arr

    def get_document(self):  # noqa: ANN201 - duck-typed stand-in
        return self

    def set_encryption_dictionary(self, enc: PDEncryption) -> None:
        self.encryption = enc


@pytest.mark.parametrize(
    ("key_bits", "prefer_aes"),
    [(128, True), (256, False)],
)
def test_end_to_end_aes_reload_roundtrip(key_bits: int, prefer_aes: bool) -> None:
    perms = AccessPermission()
    policy = StandardProtectionPolicy("owner-pw", "user-pw", perms)
    policy.set_encryption_key_length(key_bits)
    policy.set_prefer_aes(prefer_aes)

    writer = StandardSecurityHandler(policy)
    doc = _FakeDoc()
    writer.prepare_document(doc)
    enc = doc.encryption
    assert enc is not None

    plain = b"end to end AES payload spanning multiple cipher blocks here!!"
    cipher_blob = writer.encrypt_stream(plain, 17, 0)
    assert cipher_blob != plain

    reader = StandardSecurityHandler()
    material = StandardDecryptionMaterial("user-pw")
    reader.prepare_for_decryption(enc, doc.get_document_id(), material)
    assert reader.decrypt_stream(cipher_blob, 17, 0) == plain
