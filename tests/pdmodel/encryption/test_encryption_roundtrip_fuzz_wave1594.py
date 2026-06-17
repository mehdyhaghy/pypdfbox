"""Fuzz-style end-to-end encryption round-trips (wave 1594).

Each case follows the full PDFBox lifecycle:

    build in-memory PDDocument
        -> protect(StandardProtectionPolicy)
        -> save to bytes (writer's encryption pipeline ciphers streams + strings)
        -> load(password) and verify the recovered content == original.

Variants exercised, matched against Apache PDFBox 3.0.7 behaviour:

* RC4 40-bit (R2), RC4 128-bit (R3), AES-128 (R4 / V4 / AESV2),
  AES-256 (R6 / V5 / AESV3).
* User password and owner password both unlock the file.
* A wrong password is rejected with ``InvalidPasswordException``.
* ``AccessPermission`` flags (can_print / can_modify / ...) round-trip and
  the user-load is read-only when modification is denied; the owner-load
  reports owner permission.
* ``set_all_security_to_be_removed(True)`` produces an unencrypted save.
* An empty (blank) user password yields owner-only protection that opens
  with the empty string but rejects an arbitrary wrong password.
* The /Encrypt dict and /ID array are present after an encrypted save.
* Indirect-object strings (the /Info /Title) are enciphered and recover.
* The /EncryptMetadata flag propagates onto the on-the-wire dictionary.

Cross-platform: every ``PDDocument`` is closed before its bytes are reused;
no temp files are unlinked, so there is no open-handle/Windows hazard.
"""

from __future__ import annotations

import io

import pytest

pytest.importorskip("pypdfbox.pdmodel.encryption.standard_security_handler")
pytest.importorskip("pypdfbox.pdmodel.encryption.standard_protection_policy")

from pypdfbox import Loader, PDDocument  # noqa: E402
from pypdfbox.cos import COSStream  # noqa: E402
from pypdfbox.pdmodel import PDPage  # noqa: E402
from pypdfbox.pdmodel.encryption.access_permission import (  # noqa: E402
    AccessPermission,
)
from pypdfbox.pdmodel.encryption.standard_protection_policy import (  # noqa: E402
    StandardProtectionPolicy,
)
from pypdfbox.pdmodel.encryption.standard_security_handler import (  # noqa: E402
    InvalidPasswordException,
)

# ----------------------------------------------------------------- helpers

# (key_length_bits, prefer_aes, human-readable variant id)
_VARIANTS: list[tuple[int, bool, str]] = [
    (40, False, "rc4_40_r2"),
    (128, False, "rc4_128_r3"),
    (128, True, "aes_128_r4"),
    (256, False, "aes_256_r6"),
]


def _build(payload: bytes, title: str | None = None) -> PDDocument:
    """One page with a raw (unfiltered) /Contents stream == ``payload``.

    Raw + no /Filter means decoded bytes equal raw bytes, so the recovered
    content stream can be compared directly to ``payload``. An optional
    /Info /Title exercises indirect-string encryption.
    """
    pd = PDDocument()
    page = PDPage()
    pd.add_page(page)
    stream = COSStream()
    with stream.create_raw_output_stream() as out:
        out.write(payload)
    page.set_contents(stream)
    if title is not None:
        pd.get_document_information().set_title(title)
    return pd


def _save(pd: PDDocument) -> bytes:
    sink = io.BytesIO()
    pd.save(sink)
    return sink.getvalue()


def _first_page_contents(pd: PDDocument) -> bytes:
    """Decoded bytes of page 0's /Contents (runs the decrypt pass)."""
    from pypdfbox.cos import COSArray
    from pypdfbox.cos import COSStream as _COSStream

    page = pd.get_pages()[0]
    contents = page.get_cos_object().get_dictionary_object("Contents")
    if isinstance(contents, _COSStream):
        with contents.create_input_stream() as src:
            return src.read()
    if isinstance(contents, COSArray):
        chunks: list[bytes] = []
        for i in range(contents.size()):
            entry = contents.get_object(i)
            if isinstance(entry, _COSStream):
                with entry.create_input_stream() as src:
                    chunks.append(src.read())
        return b"\n".join(chunks)
    return b""


def _protect_and_save(
    payload: bytes,
    *,
    key_length: int,
    prefer_aes: bool,
    owner: str | None = "owner-pw",
    user: str | None = "user-pw",
    permissions: AccessPermission | None = None,
    title: str | None = None,
    encrypt_metadata: bool = True,
) -> bytes:
    pd = _build(payload, title=title)
    policy = StandardProtectionPolicy(
        owner_password=owner,
        user_password=user,
        permissions=permissions if permissions is not None else AccessPermission(),
    )
    policy.set_encryption_key_length(key_length)
    policy.set_prefer_aes(prefer_aes)
    policy.set_encrypt_metadata(encrypt_metadata)
    pd.protect(policy)
    saved = _save(pd)
    pd.close()
    return saved


# ----------------------------------------------------------------- tests


@pytest.mark.parametrize(
    ("key_length", "prefer_aes", "vid"),
    _VARIANTS,
    ids=[v[2] for v in _VARIANTS],
)
def test_user_password_round_trip(key_length: int, prefer_aes: bool, vid: str) -> None:
    payload = b"BT /F1 12 Tf 50 700 Td (" + vid.encode("ascii") + b") Tj ET"
    saved = _protect_and_save(payload, key_length=key_length, prefer_aes=prefer_aes)
    # Cleartext must not survive the cipher.
    assert payload not in saved
    with PDDocument.load(saved, password="user-pw") as reloaded:
        assert reloaded.is_encrypted() is True
        assert reloaded.get_number_of_pages() == 1
        assert _first_page_contents(reloaded) == payload


@pytest.mark.parametrize(
    ("key_length", "prefer_aes", "vid"),
    _VARIANTS,
    ids=[v[2] for v in _VARIANTS],
)
def test_owner_password_round_trip(key_length: int, prefer_aes: bool, vid: str) -> None:
    payload = b"owner-decrypt-" + vid.encode("ascii")
    saved = _protect_and_save(payload, key_length=key_length, prefer_aes=prefer_aes)
    with PDDocument.load(saved, password="owner-pw") as reloaded:
        assert reloaded.is_encrypted() is True
        assert _first_page_contents(reloaded) == payload
        assert reloaded.get_current_access_permission().is_owner_permission() is True


@pytest.mark.parametrize(
    ("key_length", "prefer_aes", "vid"),
    _VARIANTS,
    ids=[v[2] for v in _VARIANTS],
)
def test_wrong_password_rejected(key_length: int, prefer_aes: bool, vid: str) -> None:
    saved = _protect_and_save(b"secret", key_length=key_length, prefer_aes=prefer_aes)
    with pytest.raises(InvalidPasswordException):
        Loader.load_pdf(saved, "definitely-not-it")


@pytest.mark.parametrize(
    ("key_length", "prefer_aes", "vid"),
    _VARIANTS,
    ids=[v[2] for v in _VARIANTS],
)
def test_empty_payload_round_trip(key_length: int, prefer_aes: bool, vid: str) -> None:
    saved = _protect_and_save(b"", key_length=key_length, prefer_aes=prefer_aes)
    with PDDocument.load(saved, password="user-pw") as reloaded:
        assert _first_page_contents(reloaded) == b""


@pytest.mark.parametrize(
    ("key_length", "prefer_aes", "vid"),
    _VARIANTS,
    ids=[v[2] for v in _VARIANTS],
)
def test_indirect_string_round_trip(key_length: int, prefer_aes: bool, vid: str) -> None:
    title = "Confidential-" + vid + "-éü"
    saved = _protect_and_save(
        b"body", key_length=key_length, prefer_aes=prefer_aes, title=title
    )
    # The /Title string must be enciphered (no plaintext "Confidential").
    assert b"Confidential" not in saved
    with PDDocument.load(saved, password="user-pw") as reloaded:
        assert reloaded.get_document_information().get_title() == title


@pytest.mark.parametrize(
    ("key_length", "prefer_aes", "vid"),
    _VARIANTS,
    ids=[v[2] for v in _VARIANTS],
)
def test_encrypt_dict_and_id_present(
    key_length: int, prefer_aes: bool, vid: str
) -> None:
    saved = _protect_and_save(b"x", key_length=key_length, prefer_aes=prefer_aes)
    assert b"/Encrypt" in saved
    assert b"/ID" in saved


@pytest.mark.parametrize(
    ("key_length", "prefer_aes", "vid"),
    _VARIANTS,
    ids=[v[2] for v in _VARIANTS],
)
def test_permissions_round_trip_no_modify(
    key_length: int, prefer_aes: bool, vid: str
) -> None:
    perms = AccessPermission()
    perms.set_can_modify(False)
    perms.set_can_print(False)
    saved = _protect_and_save(
        b"locked", key_length=key_length, prefer_aes=prefer_aes, permissions=perms
    )
    with PDDocument.load(saved, password="user-pw") as reloaded:
        cap = reloaded.get_current_access_permission()
        assert cap.can_modify() is False
        assert cap.can_print() is False
        assert cap.is_read_only() is True
    # Owner login bypasses the permission gate.
    with PDDocument.load(saved, password="owner-pw") as reloaded:
        cap = reloaded.get_current_access_permission()
        assert cap.is_owner_permission() is True
        assert cap.can_modify() is True


@pytest.mark.parametrize(
    ("key_length", "prefer_aes", "vid"),
    _VARIANTS,
    ids=[v[2] for v in _VARIANTS],
)
def test_permission_flags_each_round_trip(
    key_length: int, prefer_aes: bool, vid: str
) -> None:
    perms = AccessPermission()
    perms.set_can_extract_content(False)
    perms.set_can_modify_annotations(False)
    perms.set_can_fill_in_form(False)
    perms.set_can_assemble_document(False)
    saved = _protect_and_save(
        b"flags", key_length=key_length, prefer_aes=prefer_aes, permissions=perms
    )
    with PDDocument.load(saved, password="user-pw") as reloaded:
        cap = reloaded.get_current_access_permission()
        assert cap.can_extract_content() is False
        assert cap.can_modify_annotations() is False
        assert cap.can_fill_in_form() is False
        assert cap.can_assemble_document() is False


@pytest.mark.parametrize(
    ("key_length", "prefer_aes", "vid"),
    _VARIANTS,
    ids=[v[2] for v in _VARIANTS],
)
def test_blank_user_password_owner_only(
    key_length: int, prefer_aes: bool, vid: str
) -> None:
    # Owner-only protection: blank user password, real owner password.
    saved = _protect_and_save(
        b"owner-only-body",
        key_length=key_length,
        prefer_aes=prefer_aes,
        owner="theowner",
        user="",
    )
    # Empty string opens (the user is unauthenticated).
    with PDDocument.load(saved, password="") as reloaded:
        assert reloaded.is_encrypted() is True
        assert _first_page_contents(reloaded) == b"owner-only-body"
    # The real owner password also opens.
    with PDDocument.load(saved, password="theowner") as reloaded:
        assert reloaded.get_current_access_permission().is_owner_permission() is True
    # An arbitrary wrong password is still rejected.
    with pytest.raises(InvalidPasswordException):
        Loader.load_pdf(saved, "bogus")


@pytest.mark.parametrize(
    ("key_length", "prefer_aes", "vid"),
    _VARIANTS,
    ids=[v[2] for v in _VARIANTS],
)
def test_set_all_security_to_be_removed(
    key_length: int, prefer_aes: bool, vid: str
) -> None:
    payload = b"to-be-decrypted-" + vid.encode("ascii")
    saved = _protect_and_save(payload, key_length=key_length, prefer_aes=prefer_aes)
    # Reload with the password, strip security, re-save.
    with PDDocument.load(saved, password="user-pw") as reloaded:
        reloaded.set_all_security_to_be_removed(True)
        plain = _save(reloaded)
    assert b"/Encrypt" not in plain
    # Cleartext content is recoverable without any password.
    with PDDocument.load(plain) as final:
        assert final.is_encrypted() is False
        assert _first_page_contents(final) == payload


@pytest.mark.parametrize(
    ("key_length", "prefer_aes", "vid"),
    _VARIANTS,
    ids=[v[2] for v in _VARIANTS],
)
def test_encrypt_metadata_flag_propagates(
    key_length: int, prefer_aes: bool, vid: str
) -> None:
    saved = _protect_and_save(
        b"meta", key_length=key_length, prefer_aes=prefer_aes, encrypt_metadata=False
    )
    with PDDocument.load(saved, password="user-pw") as reloaded:
        enc = reloaded.get_encryption()
        assert enc.is_encrypt_meta_data() is False


@pytest.mark.parametrize(
    ("key_length", "prefer_aes", "vid"),
    _VARIANTS,
    ids=[v[2] for v in _VARIANTS],
)
def test_security_handler_cached_after_save(
    key_length: int, prefer_aes: bool, vid: str
) -> None:
    pd = _build(b"cache")
    policy = StandardProtectionPolicy("o", "u", AccessPermission())
    policy.set_encryption_key_length(key_length)
    policy.set_prefer_aes(prefer_aes)
    pd.protect(policy)
    _ = _save(pd)
    assert pd._security_handler is not None  # noqa: SLF001
    pd.close()


def test_binary_payload_high_bytes_aes256() -> None:
    """A full 0..255 byte payload must survive the AES-256 block cipher
    (padding boundary stress)."""
    payload = bytes(range(256)) * 3
    saved = _protect_and_save(payload, key_length=256, prefer_aes=False)
    assert payload not in saved
    with PDDocument.load(saved, password="user-pw") as reloaded:
        assert _first_page_contents(reloaded) == payload


def test_id_stable_across_user_and_owner_load() -> None:
    """The /ID feeds the R2-R4 file-key derivation; both credentials must
    derive the same key off the same /ID and decrypt identically."""
    payload = b"id-bound-key"
    saved = _protect_and_save(payload, key_length=128, prefer_aes=False)
    with PDDocument.load(saved, password="user-pw") as a:
        from_user = _first_page_contents(a)
    with PDDocument.load(saved, password="owner-pw") as b:
        from_owner = _first_page_contents(b)
    assert from_user == payload
    assert from_owner == payload


def test_reencrypt_after_decrypt_round_trips() -> None:
    """Strip security, then re-protect with a different password and key
    length, and confirm the new credential round-trips (multi-cycle)."""
    payload = b"recrypt-cycle"
    saved = _protect_and_save(payload, key_length=40, prefer_aes=False)
    with PDDocument.load(saved, password="user-pw") as r:
        r.set_all_security_to_be_removed(True)
        plain = _save(r)
    # Re-load the plaintext doc and protect afresh with AES-256.
    with PDDocument.load(plain) as r2:
        r2.set_all_security_to_be_removed(False)
        policy = StandardProtectionPolicy("newowner", "newuser", AccessPermission())
        policy.set_encryption_key_length(256)
        r2.protect(policy)
        recrypted = _save(r2)
    assert b"/Encrypt" in recrypted
    with PDDocument.load(recrypted, password="newuser") as final:
        assert final.is_encrypted() is True
        assert _first_page_contents(final) == payload
