"""Forward-ports of PDFBox 3.0.9 encryption fixes (wave 1616).

* PDFBOX-6329: a missing /U or /O raises ``OSError`` ("/Encrypt/U entry is
  missing" / "/Encrypt/O entry is missing") instead of a wrong-password error.
* PDFBOX-6316: a key length below 5 bytes (``/Length`` < 40 for V != 1) raises
  ``OSError("Invalid encryption dictionary length: N")``; V=1 always uses a
  5-byte key, whatever /Length says.
* PDFBOX-6313: ``PDEncryption.has_security_handler`` is no longer inverted.
* PDFBOX-6314: ``SaslPrep.prohibited`` no longer narrows astral code points.

Malformed inputs also go through ``PDDocument.load`` to make sure no
low-level exception (IndexError, ValueError, TypeError) escapes.
"""

import contextlib
import io

import pytest

from pypdfbox import PDDocument
from pypdfbox.pdmodel import PDPage
from pypdfbox.pdmodel.encryption.access_permission import AccessPermission
from pypdfbox.pdmodel.encryption.invalid_password_exception import (
    InvalidPasswordException,
)
from pypdfbox.pdmodel.encryption.pd_encryption import PDEncryption
from pypdfbox.pdmodel.encryption.sasl_prep import SaslPrep
from pypdfbox.pdmodel.encryption.standard_protection_policy import (
    StandardProtectionPolicy,
)
from pypdfbox.pdmodel.encryption.standard_security_handler import (
    StandardDecryptionMaterial,
    StandardSecurityHandler,
)

_DOC_ID = b"0123456789abcdef"


def _encryption(
    v: int,
    r: int,
    length: int | None = 128,
    *,
    o: bytes | None = b"\x00" * 32,
    u: bytes | None = b"\x00" * 32,
) -> PDEncryption:
    enc = PDEncryption()
    enc.set_filter("Standard")
    enc.set_v(v)
    enc.set_revision(r)
    if length is not None:
        enc.set_length(length)
    enc.set_p(-4)
    if o is not None:
        enc.set_o(o)
    if u is not None:
        enc.set_u(u)
    return enc


def _prepare(enc: PDEncryption, password: str = "") -> StandardSecurityHandler:
    handler = StandardSecurityHandler()
    handler.prepare_for_decryption(
        enc, _DOC_ID, StandardDecryptionMaterial(password)
    )
    return handler


def _protected(key_length: int, user_password: str = "user") -> bytes:
    doc = PDDocument()
    doc.add_page(PDPage())
    policy = StandardProtectionPolicy(
        owner_password="owner",
        user_password=user_password,
        permissions=AccessPermission(),
    )
    policy.set_encryption_key_length(key_length)
    doc.protect(policy)
    sink = io.BytesIO()
    doc.save(sink)
    doc.close()
    return sink.getvalue()


def _patch_encrypt_dict(data: bytes, old: bytes, new: bytes) -> bytes:
    """Length-preserving edit inside the /Encrypt dictionary only."""
    assert len(old) == len(new)
    start = data.index(b"/Filter /Standard")
    end = data.index(b">>", start)
    region = data[start:end]
    assert old in region
    return data[:start] + region.replace(old, new, 1) + data[end:]


# --------------------------------------------------------------------------- #
# PDFBOX-6329: missing /U or /O                                               #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(("v", "r"), [(1, 2), (2, 3), (4, 4), (5, 5), (5, 6)])
def test_missing_u_raises_io_error(v: int, r: int) -> None:
    enc = _encryption(v, r, 256 if r >= 5 else 128, u=None)
    with pytest.raises(OSError, match="^/Encrypt/U entry is missing$") as info:
        _prepare(enc)
    assert not isinstance(info.value, InvalidPasswordException)


@pytest.mark.parametrize(("v", "r"), [(1, 2), (2, 3), (4, 4), (5, 5), (5, 6)])
def test_missing_o_raises_io_error(v: int, r: int) -> None:
    enc = _encryption(v, r, 256 if r >= 5 else 128, o=None)
    with pytest.raises(OSError, match="^/Encrypt/O entry is missing$") as info:
        _prepare(enc)
    assert not isinstance(info.value, InvalidPasswordException)


def test_missing_u_reported_before_missing_o() -> None:
    with pytest.raises(OSError, match="/Encrypt/U entry is missing"):
        _prepare(_encryption(2, 3, o=None, u=None))


def test_missing_entry_checked_before_password_preparation() -> None:
    # Upstream checks /U and /O before SaslPrep; a prohibited R6 password
    # must not mask the malformed dictionary.
    enc = _encryption(5, 6, 256, u=None)
    with pytest.raises(OSError, match="/Encrypt/U entry is missing"):
        _prepare(enc, "\u0007")


@pytest.mark.parametrize("key", [b"/U", b"/O"], ids=["U", "O"])
@pytest.mark.parametrize("key_length", [40, 128, 256])
def test_load_with_missing_entry_raises_io_error(key: bytes, key_length: int) -> None:
    data = _protected(key_length)
    data = _patch_encrypt_dict(data, b"\n" + key + b" <", b"\n/X <")
    with pytest.raises(OSError, match=f"/Encrypt{key.decode()} entry is missing"):
        PDDocument.load(data, "user")


@pytest.mark.parametrize(
    ("v", "r", "length", "o", "u"),
    [
        (2, 3, 128, b"", b""),
        (2, 3, 128, b"a", b"b"),
        (4, 4, 128, b"a", b"b"),
        (5, 5, 256, b"a" * 40, b"b" * 40),
        (5, 6, 256, b"a", b"b"),
        (5, 6, 256, b"", b""),
    ],
    ids=["r3_empty", "r3_short", "r4_short", "r5_short", "r6_short", "r6_empty"],
)
def test_short_o_and_u_are_wrong_password(v, r, length, o, u) -> None:
    # Upstream pads /O and /U (getOwnerKey/getUserKey) so short values are
    # simply wrong passwords, never an index error.
    for password in ("", "user"):
        with pytest.raises(InvalidPasswordException):
            _prepare(_encryption(v, r, length, o=o, u=u), password)


@pytest.mark.parametrize("entry", ["oe", "ue", "perms"])
@pytest.mark.parametrize("size", [0, 1, 5, 31])
def test_short_r6_key_entries_do_not_leak_low_level_errors(
    entry: str, size: int
) -> None:
    doc = PDDocument()
    doc.add_page(PDPage())
    policy = StandardProtectionPolicy(
        owner_password="owner", user_password="user", permissions=AccessPermission()
    )
    policy.set_encryption_key_length(256)
    handler = StandardSecurityHandler(policy)
    handler.prepare_document_for_encryption(doc)
    enc = doc.get_encryption()
    getattr(enc, "set_" + entry)(getattr(enc, "get_" + entry)()[:size])
    for password in ("user", "owner", "wrong"):
        # Wrong password or missing /OE /UE: upstream IOException.
        with contextlib.suppress(OSError):
            _prepare(enc, password)
    doc.close()


# --------------------------------------------------------------------------- #
# PDFBOX-6316: key length below 5 bytes                                       #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("v", "r", "length"),
    [(2, 3, 0), (2, 3, 8), (2, 3, 39), (2, 3, -8), (4, 4, 32), (5, 6, 8)],
)
def test_small_length_raises_io_error(v: int, r: int, length: int) -> None:
    enc = _encryption(v, r, length, o=b"\x00" * 48, u=b"\x00" * 48)
    with pytest.raises(
        OSError, match=f"^Invalid encryption dictionary length: {length}$"
    ) as info:
        _prepare(enc)
    assert not isinstance(info.value, InvalidPasswordException)


def test_minimum_length_is_accepted_as_a_candidate() -> None:
    # /Length 40 passes the length gate; all-zero /O,/U is a wrong password.
    with pytest.raises(InvalidPasswordException):
        _prepare(_encryption(2, 3, 40))


@pytest.mark.parametrize("length", [7, 0, 128])
def test_v1_ignores_length(length: int) -> None:
    # V=1 always derives a 5-byte key; a bogus /Length used to reach the RC4
    # derivation and fail with a low-level ValueError.
    with pytest.raises(InvalidPasswordException):
        _prepare(_encryption(1, 2, length))


def test_load_v1_document_with_bogus_length_still_opens() -> None:
    data = _protected(40)
    data = _patch_encrypt_dict(data, b"/Length 40", b"/Length 07")
    with PDDocument.load(data, "user") as doc:
        assert doc.is_encrypted()
        assert doc.get_number_of_pages() == 1


@pytest.mark.parametrize("key_length", [128, 256])
def test_load_with_small_length_raises_io_error(key_length: int) -> None:
    data = _protected(key_length)
    old = f"/Length {key_length}".encode("ascii")
    new = b"/Length " + b"8".rjust(len(str(key_length)), b"0")
    data = _patch_encrypt_dict(data, old, new)
    with pytest.raises(OSError, match="Invalid encryption dictionary length: 8"):
        PDDocument.load(data, "user")


# --------------------------------------------------------------------------- #
# PDFBOX-6313: has_security_handler                                           #
# --------------------------------------------------------------------------- #


def test_has_security_handler_reports_installed_handler() -> None:
    enc = PDEncryption()
    assert enc.has_security_handler() is False
    enc.set_security_handler(StandardSecurityHandler())
    assert enc.has_security_handler() is True


def test_has_security_handler_on_loaded_document() -> None:
    with PDDocument.load(_protected(128), "user") as doc:
        enc = doc.get_encryption()
        try:
            enc.get_security_handler()
            installed = True
        except OSError:
            installed = False
        assert enc.has_security_handler() is installed


# --------------------------------------------------------------------------- #
# PDFBOX-6314: astral code points in passwords                                #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "cp", [0x10000, 0x12000, 0x13000, 0x100A0, 0x1F600], ids=lambda cp: f"U+{cp:04X}"
)
def test_astral_password_code_point_not_prohibited(cp: int) -> None:
    assert not SaslPrep.prohibited(cp)
    password = "pw" + chr(cp)
    assert SaslPrep.sasl_prep_query(password) == password
    assert SaslPrep.sasl_prep_stored(password) == password


@pytest.mark.parametrize(
    "cp", [0x00A0, 0x2000, 0x3000, 0x0000, 0x001F, 0x007F],
    ids=lambda cp: f"U+{cp:04X}",
)
def test_bmp_space_and_control_still_prohibited(cp: int) -> None:
    assert SaslPrep.prohibited(cp)


def test_astral_still_prohibited_by_other_tables() -> None:
    # Private use, noncharacter and tagging checks keep the full code point.
    for cp in (0xF0000, 0x10FFFD, 0x1FFFE, 0xE0001, 0x1D173):
        assert SaslPrep.prohibited(cp)


def test_r6_document_with_astral_password_round_trips() -> None:
    password = "\U00012000pw\U00010000"
    data = _protected(256, user_password=password)
    with PDDocument.load(data, password) as doc:
        assert doc.is_encrypted()
        assert doc.get_number_of_pages() == 1
    with pytest.raises(InvalidPasswordException):
        PDDocument.load(data, "pw")
