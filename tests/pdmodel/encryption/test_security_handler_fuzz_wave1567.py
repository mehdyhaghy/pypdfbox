"""Wave 1567 fuzz/parity battery for the Standard Security Handler.

Hammers the key-derivation + permission-bit + password-padding surfaces of
``StandardSecurityHandler`` / ``AccessPermission`` / ``StandardProtectionPolicy``
/ ``PDEncryption`` against the upstream PDFBox 3.0.7 semantics:

* RC4 vs AES across /V 1,2,4,5 and /R 2,3,4,6 — key-length derivation, the
  bits-vs-bytes split, and a full encrypt → reload → decrypt round trip per
  revision.
* Permission-bit packing/unpacking through ``AccessPermission`` — the reserved
  low bits (positions 1 and 2) and the high "all set" default.
* The 32-byte PDF password pad (Algorithm 2 step a) and the r6 127-byte
  truncation.
* ``/P`` round-tripped as a signed 32-bit two's-complement int, including
  negative values and unsigned spellings of the same bit pattern.
* Empty / over-long passwords (truncation to 32 bytes for r<=4, 127 bytes for
  r6).
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSString
from pypdfbox.pdmodel.encryption.access_permission import AccessPermission
from pypdfbox.pdmodel.encryption.pd_encryption import PDEncryption
from pypdfbox.pdmodel.encryption.standard_protection_policy import (
    StandardProtectionPolicy,
)
from pypdfbox.pdmodel.encryption.standard_security_handler import (
    _PASSWORD_PADDING,
    StandardDecryptionMaterial,
    StandardSecurityHandler,
    _signed32,
)

H = StandardSecurityHandler


# --------------------------------------------------------------------------
# A minimal document stand-in that records /ID and accepts /Encrypt, so we can
# drive prepare_document (write) → reload (read) without the full PDDocument.
# --------------------------------------------------------------------------
class _FakeDoc:
    def __init__(self, doc_id: bytes = b"\x01" * 16) -> None:
        self._id = doc_id
        self.encryption: PDEncryption | None = None

    # prepare_document pulls /ID[0] via _extract_document_id, which expects a
    # COSArray whose element 0 is a COSString.
    def get_document_id(self) -> COSArray:
        arr = COSArray()
        arr.add(COSString(self._id))
        return arr

    def get_document(self):  # noqa: ANN201 - duck-typed
        return self

    def set_encryption_dictionary(self, enc: PDEncryption) -> None:
        self.encryption = enc


def _roundtrip_handler(
    owner: str,
    user: str,
    key_bits: int,
    prefer_aes: bool,
    doc_id: bytes = b"\x01" * 16,
    perms: AccessPermission | None = None,
):
    """Encrypt with one handler, return (write_handler, encryption, doc_id)."""
    policy = StandardProtectionPolicy(owner, user, perms or AccessPermission())
    policy.set_encryption_key_length(key_bits)
    policy.set_prefer_aes(prefer_aes)
    handler = H(policy)
    doc = _FakeDoc(doc_id)
    handler.prepare_document(doc)
    return handler, doc.encryption, doc_id


# ============================================================ key-len derivation


@pytest.mark.parametrize(
    ("key_bits", "prefer_aes", "exp_rev", "exp_ver"),
    [
        (40, False, 3, 1),    # default AccessPermission has r3 bits → R3, V1
        (128, False, 3, 2),   # RC4-128
        (128, True, 4, 4),    # AES-128
        (256, False, 6, 5),   # AES-256
        (256, True, 6, 5),    # 256 ignores prefer_aes
    ],
)
def test_revision_version_from_keylength(key_bits, prefer_aes, exp_rev, exp_ver):
    _, enc, _ = _roundtrip_handler("own", "usr", key_bits, prefer_aes)
    assert enc.get_revision() == exp_rev
    assert enc.get_v() == exp_ver


def test_compute_revision_number_static():
    assert H.compute_revision_number(256) == 6
    assert H.compute_revision_number(128, prefer_aes=True) == 4
    assert H.compute_revision_number(128, prefer_aes=False) == 3
    assert H.compute_revision_number(40) == 2


def test_compute_revision_from_version_v5_is_r6():
    handler = H(StandardProtectionPolicy("o", "u"))
    assert handler.compute_revision_number_from_version(5) == 6
    assert handler.compute_revision_number_from_version(4) == 4


def test_key_length_stored_in_bits_not_bytes():
    # /Length is bits on the wire (40/128/256), key derivation divides by 8.
    _, enc, _ = _roundtrip_handler("o", "u", 128, False)
    assert enc.get_length() == 128
    _, enc256, _ = _roundtrip_handler("o", "u", 256, False)
    assert enc256.get_length() == 256


# ============================================================ password padding


def test_password_padding_constant_is_32_bytes():
    assert len(_PASSWORD_PADDING) == 32
    assert _PASSWORD_PADDING[0] == 0x28
    assert _PASSWORD_PADDING[-1] == 0x7A


def test_pad_empty_password_is_full_pad():
    assert H._pad_password(b"") == _PASSWORD_PADDING


def test_pad_password_pads_to_32():
    padded = H._pad_password(b"abc")
    assert len(padded) == 32
    assert padded[:3] == b"abc"
    assert padded[3:] == _PASSWORD_PADDING[: 32 - 3]


@pytest.mark.parametrize("length", [0, 1, 16, 31, 32, 33, 64, 200])
def test_pad_password_always_32(length):
    assert len(H._pad_password(b"x" * length)) == 32


def test_overlong_password_truncates_to_32_for_r4():
    # r<=4: only the first 32 bytes of the password matter (pad takes [:32]).
    long_pw = b"A" * 100
    assert H._pad_password(long_pw) == H._pad_password(long_pw[:32])
    # Bytes 32..99 do not affect the pad.
    assert H._pad_password(b"A" * 32 + b"ZZZ") == H._pad_password(b"A" * 32)


# ============================================================ r6 truncation


def test_truncate_127_r6():
    assert H.truncate_127(b"a" * 200) == b"a" * 127
    assert len(H.truncate_127(b"a" * 200)) == 127
    assert H.truncate_127(b"short") == b"short"
    assert H.truncate_127(None) == b""


def test_truncate_127_boundary():
    assert H.truncate_127(b"x" * 127) == b"x" * 127
    assert H.truncate_127(b"x" * 128) == b"x" * 127


# ============================================================ /P signed 32-bit


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (-4, -4),
        (-44, -44),
        (0xFFFFFFFC, -4),         # unsigned spelling of -4
        (0xFFFFFFFF, -1),
        (0, 0),
        (0x7FFFFFFF, 0x7FFFFFFF),
        (0x80000000, -0x80000000),
        (-3904, -3904),           # DEFAULT_PERMISSIONS
        (-1, -1),
    ],
)
def test_signed32_roundtrip(value, expected):
    assert _signed32(value) == expected
    # Idempotent.
    assert _signed32(_signed32(value)) == expected


def test_p_roundtrip_through_pd_encryption_negative():
    enc = PDEncryption()
    for p in (-4, -44, -3904, -1, 12345, -2147483648, 2147483647):
        enc.set_p(p)
        assert enc.get_p() == p
        assert enc.get_permissions() == p


def test_p_high_bits_signed_in_key_derivation():
    # The struct.pack("<i", _signed32(p)) inside Algorithm 2 must accept any
    # unsigned spelling of a negative /P (PDFBox writes /P as a signed int32).
    # A handler built from /P == 0xFFFFFFFC (== -4) must derive the same key
    # as one built from -4 directly.
    doc_id = b"\x07" * 16
    perm_neg = AccessPermission(-4)
    perm_uns = AccessPermission(0xFFFFFFFC)
    _, enc_neg, _ = _roundtrip_handler(
        "o", "u", 128, False, doc_id, perm_neg
    )
    _, enc_uns, _ = _roundtrip_handler(
        "o", "u", 128, False, doc_id, perm_uns
    )
    # /U is derived from the file key which mixes in struct.pack of signed /P;
    # both spellings must collapse to the same /U.
    assert enc_neg.get_u() == enc_uns.get_u()


# ============================================================ AccessPermission bits


def test_default_permissions_high_bits_set():
    ap = AccessPermission()
    # ~3 == -4: every bit except reserved positions 1,2.
    assert ap.get_permission_bytes() == -4
    assert ap.can_print()
    assert ap.can_modify()
    assert ap.can_extract_content()
    assert ap.can_print_faithful()
    # Reserved low bits (1-based positions 1,2) must be clear.
    assert not ap.is_permission_bit_on(1)
    assert not ap.is_permission_bit_on(2)


def test_explicit_minus_one_is_kept_verbatim():
    # Upstream AccessPermission(-1) stays -1, NOT coerced to -4.
    assert AccessPermission(-1).get_permission_bytes() == -1
    # No-arg ctor → DEFAULT_PERMISSIONS (-4).
    assert AccessPermission().get_permission_bytes() == -4


@pytest.mark.parametrize(
    ("setter", "getter", "bit_pos"),
    [
        ("set_can_print", "can_print", 3),
        ("set_can_modify", "can_modify", 4),
        ("set_can_extract_content", "can_extract_content", 5),
        ("set_can_modify_annotations", "can_modify_annotations", 6),
        ("set_can_fill_in_form", "can_fill_in_form", 9),
        ("set_can_extract_for_accessibility", "can_extract_for_accessibility", 10),
        ("set_can_assemble_document", "can_assemble_document", 11),
        ("set_can_print_faithful", "can_print_faithful", 12),
    ],
)
def test_permission_bit_pack_unpack(setter, getter, bit_pos):
    ap = AccessPermission(0)  # all clear
    assert not getattr(ap, getter)()
    getattr(ap, setter)(True)
    assert getattr(ap, getter)()
    # The exact 1-based bit position must be the one that flipped.
    assert ap.get_permission_bytes() == (1 << (bit_pos - 1))
    getattr(ap, setter)(False)
    assert ap.get_permission_bytes() == 0


def test_read_only_blocks_typed_setters():
    ap = AccessPermission(0)
    ap.set_read_only()
    ap.set_can_print(True)
    assert not ap.can_print()  # no-op under read-only


def test_from_bytes_sign_extends_high_byte():
    # 0xFFFFFFFF → -1 (signed 4-byte big-endian).
    assert AccessPermission.from_bytes(b"\xff\xff\xff\xff").get_permission_bytes() == -1
    # 0x00000004 → 4 (print bit only, positive).
    assert AccessPermission.from_bytes(b"\x00\x00\x00\x04").get_permission_bytes() == 4
    with pytest.raises(ValueError, match="4 bytes"):
        AccessPermission.from_bytes(b"\x00\x00")


def test_owner_access_permission_full():
    owner = AccessPermission.get_owner_access_permission()
    assert owner.is_owner_permission()
    assert owner.get_permission_bytes() == -4


def test_public_key_permission_bytes_mutation():
    # get_permission_bytes_for_public_key: bit1 ON, bits 7,8 OFF, bits 13..32 OFF.
    ap = AccessPermission(-1)  # all bits set
    val = ap.get_permission_bytes_for_public_key()
    assert val & 0x1  # bit 1 (1-based) set
    assert not (val & (1 << 6))  # bit 7 clear
    assert not (val & (1 << 7))  # bit 8 clear
    assert val <= 0x00000FFF  # high bits cleared


# ============================================================ full round-trips


@pytest.mark.parametrize(
    ("key_bits", "prefer_aes"),
    [
        (40, False),    # RC4-40 / V1 R3
        (128, False),   # RC4-128 / V2 R3
        (128, True),    # AES-128 / V4 R4
        (256, False),   # AES-256 / V5 R6
        (256, True),
    ],
)
def test_owner_and_user_password_authenticate(key_bits, prefer_aes):
    owner, user = "ownerpw", "userpw"
    doc_id = b"\x02" * 16
    _, enc, _ = _roundtrip_handler(owner, user, key_bits, prefer_aes, doc_id)
    # Owner password authenticates.
    assert H.is_owner_password(owner, enc, doc_id)
    # User password authenticates.
    assert H.is_user_password(user, enc, doc_id)
    # A wrong password fails on both checks.
    assert not H.is_owner_password("nope", enc, doc_id)
    assert not H.is_user_password("nope", enc, doc_id)


@pytest.mark.parametrize("key_bits", [40, 128])
def test_empty_user_password_roundtrip(key_bits):
    # Empty user password + owner-only protection: empty user pw must open.
    doc_id = b"\x09" * 16
    _, enc, _ = _roundtrip_handler("theowner", "", key_bits, False, doc_id)
    assert H.is_user_password("", enc, doc_id)
    assert H.is_owner_password("theowner", enc, doc_id)


def test_overlong_password_truncated_still_authenticates_r4():
    # r4: password truncated to 32 bytes. A 100-char password and its first
    # 32 chars authenticate identically because only [:32] is hashed.
    long_pw = "A" * 100
    doc_id = b"\x03" * 16
    _, enc, _ = _roundtrip_handler(long_pw, long_pw, 128, True, doc_id)
    assert H.is_user_password(long_pw, enc, doc_id)
    # The 32-char prefix authenticates as the same user password (truncation).
    assert H.is_user_password("A" * 32, enc, doc_id)


def test_overlong_password_truncated_to_127_r6():
    long_pw = "B" * 200
    doc_id = b"\x04" * 16
    _, enc, _ = _roundtrip_handler(long_pw, long_pw, 256, False, doc_id)
    assert H.is_user_password(long_pw, enc, doc_id)
    # 127-char prefix authenticates as the same (r6 truncate127).
    assert H.is_user_password("B" * 127, enc, doc_id)


def test_full_decrypt_with_decryption_material_r4():
    owner, user = "secretowner", "secretuser"
    doc_id = b"\x05" * 16
    write_handler, enc, _ = _roundtrip_handler(owner, user, 128, True, doc_id)
    plaintext = b"Hello encrypted world! " * 4
    ct = write_handler.encrypt_string(plaintext, 7, 0)
    assert ct != plaintext

    # Reload: a fresh handler authenticates with the user password and decrypts.
    read_handler = H()
    read_handler.prepare_for_decryption(
        enc, doc_id, StandardDecryptionMaterial(user)
    )
    assert read_handler.decrypt_string(ct, 7, 0) == plaintext


def test_full_decrypt_with_decryption_material_r6():
    owner, user = "owner256", "user256"
    doc_id = b"\x06" * 16
    write_handler, enc, _ = _roundtrip_handler(owner, user, 256, False, doc_id)
    plaintext = b"AES-256 round trip payload " * 3
    ct = write_handler.encrypt_string(plaintext, 11, 0)

    read_handler = H()
    read_handler.prepare_for_decryption(
        enc, doc_id, StandardDecryptionMaterial(user)
    )
    assert read_handler.decrypt_string(ct, 11, 0) == plaintext


def test_owner_decrypt_grants_full_permissions():
    owner, user = "ownerfull", "userlimited"
    doc_id = b"\x08" * 16
    # Restrict user permissions to print-only.
    perm = AccessPermission(0)
    perm.set_can_print(True)
    _, enc, _ = _roundtrip_handler(owner, user, 128, True, doc_id, perm)

    read_handler = H()
    read_handler.prepare_for_decryption(
        enc, doc_id, StandardDecryptionMaterial(owner)
    )
    ap = read_handler.get_current_access_permission()
    assert ap.is_owner_permission()


def test_user_decrypt_limited_permissions_readonly():
    owner, user = "ownerx", "userx"
    doc_id = b"\x0a" * 16
    perm = AccessPermission(0)
    perm.set_can_print(True)
    _, enc, _ = _roundtrip_handler(owner, user, 128, True, doc_id, perm)

    read_handler = H()
    read_handler.prepare_for_decryption(
        enc, doc_id, StandardDecryptionMaterial(user)
    )
    ap = read_handler.get_current_access_permission()
    assert ap.is_read_only()
    assert ap.can_print()
    assert not ap.can_modify()


# ============================================================ misc parity


def test_compute_owner_password_r2_requires_5_byte_key():
    with pytest.raises(OSError, match="Expected length=5"):
        H.compute_owner_password(b"owner", b"user", 2, 16)


def test_get_user_password_out_of_range_revision_is_empty():
    assert H.get_user_password(b"o", b"\x00" * 32, 7, 16) == b""
    assert H.get_user_password(b"o", b"\x00" * 32, 0, 16) == b""


def test_compute_user_password_r5_r6_returns_empty():
    # r5/r6 have no recoverable plaintext user password.
    assert H.compute_user_password(b"pw", b"o", -4, b"id", 5, 32) == b""
    assert H.compute_user_password(b"pw", b"o", -4, b"id", 6, 32) == b""
