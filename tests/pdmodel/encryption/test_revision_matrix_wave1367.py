"""Wave 1367 — full per-revision round-trip matrix for the standard
security handler, plus extra ``PublicKeySecurityHandler`` envelope
variations.

The pre-existing ``test_encryption_roundtrip.py`` exercises a single path
(r3 RC4-128 by default). This wave widens coverage to:

* R2 (RC4-40 — ``key_length=40``)
* R3 (RC4-128 — ``key_length=128``, ``prefer_aes=False``)
* R4 (AES-128 CBC — ``key_length=128``, ``prefer_aes=True``, V=4 crypt filters)
* R5 (AES-256 Adobe Extension Level 3 — produced via a hand-built
  ``PDEncryption`` dict because :class:`StandardProtectionPolicy` upgrades
  ``key_length=256`` to r6; the r5 *read* path is the only surface left
  to exercise)
* R6 (AES-256 per PDF 2.0 — ``key_length=256``)

For each revision we round-trip:

* a literal payload baked into the page's content stream;
* a ``COSString`` slot in the document information dictionary (``/Title``);
* (where the writer surfaces it) a ``/Metadata`` stream on the catalog.

Owner-password reads, user-password reads, wrong-password rejection, and
``AccessPermission`` flag propagation are checked for every revision.
"""

from __future__ import annotations

import datetime
import io

import pytest

# Skip on checkouts that don't have the security cluster present yet.
pytest.importorskip("pypdfbox.pdmodel.encryption.standard_security_handler")
pytest.importorskip("pypdfbox.pdmodel.encryption.standard_protection_policy")

from pypdfbox import Loader, PDDocument  # noqa: E402
from pypdfbox.cos import COSArray, COSStream  # noqa: E402
from pypdfbox.pdmodel import PDPage  # noqa: E402
from pypdfbox.pdmodel.common.pd_metadata import PDMetadata  # noqa: E402
from pypdfbox.pdmodel.encryption.access_permission import (  # noqa: E402
    AccessPermission,
)
from pypdfbox.pdmodel.encryption.pd_encryption import PDEncryption  # noqa: E402
from pypdfbox.pdmodel.encryption.public_key_decryption_material import (  # noqa: E402
    PublicKeyDecryptionMaterial,
)
from pypdfbox.pdmodel.encryption.public_key_protection_policy import (  # noqa: E402
    PublicKeyProtectionPolicy,
)
from pypdfbox.pdmodel.encryption.public_key_recipient import (  # noqa: E402
    PublicKeyRecipient,
)
from pypdfbox.pdmodel.encryption.public_key_security_handler import (  # noqa: E402
    PublicKeySecurityHandler,
)
from pypdfbox.pdmodel.encryption.standard_protection_policy import (  # noqa: E402
    StandardProtectionPolicy,
)
from pypdfbox.pdmodel.encryption.standard_security_handler import (  # noqa: E402
    InvalidPasswordException,
    StandardSecurityHandler,
)

# --------------------------------------------------------------- helpers


_CONTENT_PAYLOAD = b"BT /F1 12 Tf 50 700 Td (Wave1367 revision round-trip) Tj ET"
_TITLE_LITERAL = "Wave 1367 revision round-trip title"
_METADATA_XML = (
    b"<?xpacket begin='\xef\xbb\xbf' id='W5M0MpCehiHzreSzNTczkc9d'?>\n"
    b"<x:xmpmeta xmlns:x='adobe:ns:meta/'><rdf:RDF "
    b"xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'/>"
    b"</x:xmpmeta>\n<?xpacket end='r'?>"
)


def _build_document(
    *,
    add_metadata: bool = True,
    title: str | None = _TITLE_LITERAL,
) -> tuple[PDDocument, bytes]:
    """Build a fresh ``PDDocument`` with a content stream, a /Title in
    /Info, and (optionally) a /Metadata stream on the catalog."""
    pd = PDDocument()
    page = PDPage()
    pd.add_page(page)

    stream = COSStream()
    with stream.create_raw_output_stream() as out:
        out.write(_CONTENT_PAYLOAD)
    page.set_contents(stream)

    if title is not None:
        info = pd.get_document_information()
        info.set_title(title)

    if add_metadata:
        meta_stream = COSStream()
        with meta_stream.create_raw_output_stream() as out:
            out.write(_METADATA_XML)
        # Stamp /Type /Metadata so the encryption-skip logic in
        # COSWriter.visit_from_stream + COSStream.set_security_handler can
        # recognise this as a metadata stream when /EncryptMetadata=false.
        # PDMetadata(COSStream) intentionally leaves the type unset
        # (matching upstream), so we set it here.
        from pypdfbox.cos import COSName

        meta_stream.set_name(COSName.TYPE, "Metadata")
        meta_stream.set_name(COSName.SUBTYPE, "XML")
        meta = PDMetadata(meta_stream)
        pd.get_document_catalog().set_metadata(meta)

    return pd, _CONTENT_PAYLOAD


def _save_protected(
    pd: PDDocument,
    owner_password: str,
    user_password: str,
    permissions: AccessPermission,
    *,
    key_length: int,
    prefer_aes: bool,
) -> bytes:
    policy = StandardProtectionPolicy(
        owner_password=owner_password,
        user_password=user_password,
        permissions=permissions,
    )
    policy.set_encryption_key_length(key_length)
    policy.set_prefer_aes(prefer_aes)
    pd.protect(policy)
    sink = io.BytesIO()
    pd.save(sink)
    return sink.getvalue()


def _first_page_contents(pd: PDDocument) -> bytes:
    page = pd.get_pages()[0]
    contents = page.get_cos_object().get_dictionary_object("Contents")
    if isinstance(contents, COSStream):
        with contents.create_input_stream() as src:
            return src.read()
    if isinstance(contents, COSArray):
        chunks: list[bytes] = []
        for i in range(contents.size()):
            entry = contents.get_object(i)
            if isinstance(entry, COSStream):
                with entry.create_input_stream() as src:
                    chunks.append(src.read())
        return b"\n".join(chunks)
    return b""


def _catalog_metadata_bytes(pd: PDDocument) -> bytes | None:
    meta = pd.get_document_catalog().get_metadata()
    if meta is None:
        return None
    cos = meta.get_cos_object()
    if not isinstance(cos, COSStream):
        return None
    with cos.create_input_stream() as src:
        return src.read()


# ---------------------------------------- revision matrix parametrisation


# (label, key_length, prefer_aes, expected_revision, expected_version)
_REVISION_MATRIX: list[tuple[str, int, bool, int, int]] = [
    ("r2-rc4-40", 40, False, 2, 1),
    ("r3-rc4-128", 128, False, 3, 2),
    ("r4-aes-128", 128, True, 4, 4),
    ("r6-aes-256", 256, False, 6, 5),
]


# --------------------------------------------------------------------- tests


@pytest.mark.parametrize(
    ("label", "key_length", "prefer_aes", "exp_rev", "exp_v"),
    _REVISION_MATRIX,
    ids=[row[0] for row in _REVISION_MATRIX],
)
def test_round_trip_user_password_each_revision(
    label: str, key_length: int, prefer_aes: bool, exp_rev: int, exp_v: int
) -> None:
    """For every (R, V) pair: user-password decrypt must recover the
    payload, the /Title COSString, and the /Metadata stream byte-for-byte.

    The wave-1367 widening of the revision matrix — wave 1361 closed the
    decrypt-string crash but only covered r3. We pin the other four here.
    """
    pd, payload = _build_document()
    saved = _save_protected(
        pd,
        owner_password="ownerWave1367",
        user_password="userWave1367",
        permissions=AccessPermission(),
        key_length=key_length,
        prefer_aes=prefer_aes,
    )
    pd.close()

    # Plaintext payload must not appear verbatim in the ciphered file.
    assert _CONTENT_PAYLOAD not in saved, (
        f"{label}: cleartext leaked into saved bytes"
    )

    with PDDocument.load(saved, password="userWave1367") as reloaded:
        assert reloaded.is_encrypted() is True
        enc = reloaded.get_encryption()
        assert enc is not None
        assert enc.get_revision() == exp_rev, (
            f"{label}: expected R={exp_rev}, got R={enc.get_revision()}"
        )
        assert enc.get_v() == exp_v, (
            f"{label}: expected V={exp_v}, got V={enc.get_v()}"
        )

        # /Contents — stream body decrypts back to the original payload.
        assert _first_page_contents(reloaded) == payload

        # COSString slot — /Info /Title round-trips after decrypt.
        info = reloaded.get_document_information()
        assert info.get_title() == _TITLE_LITERAL

        # /Metadata stream survives the round trip too.
        assert _catalog_metadata_bytes(reloaded) == _METADATA_XML


@pytest.mark.parametrize(
    ("label", "key_length", "prefer_aes", "exp_rev", "exp_v"),
    _REVISION_MATRIX,
    ids=[row[0] for row in _REVISION_MATRIX],
)
def test_round_trip_owner_password_each_revision(
    label: str, key_length: int, prefer_aes: bool, exp_rev: int, exp_v: int
) -> None:
    """Owner-password reads recover the same payload + COSString + metadata
    *and* surface owner-level permissions (algorithm 7 / r5-r6 owner branch)."""
    pd, payload = _build_document()
    permissions = AccessPermission()
    permissions.set_can_print(False)  # restrict the user mask so we can tell
    permissions.set_can_modify(False)
    saved = _save_protected(
        pd,
        owner_password="ownerWave1367",
        user_password="userWave1367",
        permissions=permissions,
        key_length=key_length,
        prefer_aes=prefer_aes,
    )
    pd.close()

    with PDDocument.load(saved, password="ownerWave1367") as reloaded:
        enc = reloaded.get_encryption()
        assert enc is not None
        assert enc.get_revision() == exp_rev
        assert enc.get_v() == exp_v
        assert _first_page_contents(reloaded) == payload
        assert reloaded.get_document_information().get_title() == _TITLE_LITERAL
        assert _catalog_metadata_bytes(reloaded) == _METADATA_XML
        # Owner-pw read → full permissions regardless of the /P bits we set.
        ap = reloaded.get_current_access_permission()
        assert ap is not None
        assert ap.can_print() is True
        assert ap.can_modify() is True
        assert ap.is_owner_permission() is True


@pytest.mark.parametrize(
    ("label", "key_length", "prefer_aes", "exp_rev", "exp_v"),
    _REVISION_MATRIX,
    ids=[row[0] for row in _REVISION_MATRIX],
)
def test_user_password_propagates_restricted_permissions_each_revision(
    label: str, key_length: int, prefer_aes: bool, exp_rev: int, exp_v: int
) -> None:
    """User-pw reads surface the **restricted** mask from /P, not owner-level."""
    pd, _payload = _build_document()
    permissions = AccessPermission()
    permissions.set_can_print(False)
    permissions.set_can_modify(False)
    permissions.set_can_extract_content(False)
    saved = _save_protected(
        pd,
        owner_password="ownerWave1367",
        user_password="userWave1367",
        permissions=permissions,
        key_length=key_length,
        prefer_aes=prefer_aes,
    )
    pd.close()

    with PDDocument.load(saved, password="userWave1367") as reloaded:
        ap = reloaded.get_current_access_permission()
        assert ap is not None, f"{label}: no access permission surfaced"
        assert ap.can_print() is False
        assert ap.can_modify() is False
        assert ap.can_extract_content() is False
        # Read-only flag is set after a user-pw decrypt.
        assert ap.is_read_only() is True


@pytest.mark.parametrize(
    ("label", "key_length", "prefer_aes", "exp_rev", "exp_v"),
    _REVISION_MATRIX,
    ids=[row[0] for row in _REVISION_MATRIX],
)
def test_wrong_password_rejected_each_revision(
    label: str, key_length: int, prefer_aes: bool, exp_rev: int, exp_v: int
) -> None:
    pd, _payload = _build_document(add_metadata=False)
    saved = _save_protected(
        pd,
        owner_password="ownerWave1367",
        user_password="userWave1367",
        permissions=AccessPermission(),
        key_length=key_length,
        prefer_aes=prefer_aes,
    )
    pd.close()

    with pytest.raises(InvalidPasswordException):
        Loader.load_pdf(saved, "definitely-not-correct")


@pytest.mark.parametrize(
    ("label", "key_length", "prefer_aes", "exp_rev", "exp_v"),
    _REVISION_MATRIX,
    ids=[row[0] for row in _REVISION_MATRIX],
)
def test_blank_user_password_owner_only(
    label: str, key_length: int, prefer_aes: bool, exp_rev: int, exp_v: int
) -> None:
    """Owner-only protection (blank user pw) — opens with empty string and
    surfaces the configured /P mask."""
    pd, payload = _build_document(add_metadata=False)
    permissions = AccessPermission()
    permissions.set_can_modify(False)
    saved = _save_protected(
        pd,
        owner_password="ownerOnlyWave1367",
        user_password="",
        permissions=permissions,
        key_length=key_length,
        prefer_aes=prefer_aes,
    )
    pd.close()

    with PDDocument.load(saved, password="") as reloaded:
        assert reloaded.is_encrypted() is True
        assert _first_page_contents(reloaded) == payload
        ap = reloaded.get_current_access_permission()
        assert ap is not None
        # Anonymous (user-pw blank) read inherits the restricted mask.
        assert ap.can_modify() is False


# ----------------------------------------------------------- R5 read-only path


def _build_r5_dictionary_via_handler() -> tuple[
    StandardSecurityHandler, PDEncryption, bytes, bytes
]:
    """Build an R5 (v5/r5) /Encrypt dict reusing the r6 hash machinery and
    returning the handler + dict + (password, file_key) for callers.

    Upstream :class:`StandardSecurityHandler` upgrades r5 → r6 on the write
    side per PDF 32000-2 (the older r5 algorithm is deprecated). We mimic
    what an Adobe Extension Level 3 r5 producer would emit so we can pin
    the read path that already routes r5 through the same Hash 2K logic as
    r6 (see ``_compute_encryption_key_r5_r6``).
    """
    import os

    password = b"r5passWave1367"
    handler = StandardSecurityHandler()
    handler.set_revision(5)
    handler.set_version(5)
    handler.set_key_length(256)
    handler.set_aes(True)

    file_key = os.urandom(32)
    handler.set_encryption_key(file_key)
    handler._encrypt_metadata = True  # noqa: SLF001 — no public setter

    # Build the /U /UE /O /OE /Perms quintet exactly as the r6 dictionary
    # builder does — the r5 algorithm produces the same byte shape; the
    # only practical difference is the hash function used by Algorithm 2.B
    # (handled inside the handler via the revision argument).
    truncated = password[:127]
    u_validation_salt = os.urandom(8)
    u_key_salt = os.urandom(8)
    u_hash = handler._compute_hash_r5_r6(  # noqa: SLF001
        truncated + u_validation_salt, truncated, b"", 5
    )
    u_value = u_hash + u_validation_salt + u_key_salt

    from cryptography.hazmat.primitives.ciphers import (
        Cipher,
        algorithms,
        modes,
    )

    ue_intermediate = handler._compute_hash_r5_r6(  # noqa: SLF001
        truncated + u_key_salt, truncated, b"", 5
    )
    ue_cipher = Cipher(
        algorithms.AES(ue_intermediate), modes.CBC(b"\x00" * 16)
    ).encryptor()
    ue = ue_cipher.update(file_key) + ue_cipher.finalize()

    o_validation_salt = os.urandom(8)
    o_key_salt = os.urandom(8)
    o_hash = handler._compute_hash_r5_r6(  # noqa: SLF001
        truncated + o_validation_salt + u_value,
        truncated,
        u_value,
        5,
    )
    o_value = o_hash + o_validation_salt + o_key_salt
    oe_intermediate = handler._compute_hash_r5_r6(  # noqa: SLF001
        truncated + o_key_salt + u_value,
        truncated,
        u_value,
        5,
    )
    oe_cipher = Cipher(
        algorithms.AES(oe_intermediate), modes.CBC(b"\x00" * 16)
    ).encryptor()
    oe = oe_cipher.update(file_key) + oe_cipher.finalize()

    # /Perms — same shape as r6.
    permissions = AccessPermission().get_permission_bytes()
    perms_block = bytearray(16)
    from pypdfbox.pdmodel.encryption.standard_security_handler import (
        _signed32 as _signed,
    )

    p = _signed(permissions)
    perms_block[0] = p & 0xFF
    perms_block[1] = (p >> 8) & 0xFF
    perms_block[2] = (p >> 16) & 0xFF
    perms_block[3] = (p >> 24) & 0xFF
    perms_block[4:8] = b"\xff\xff\xff\xff"
    perms_block[8] = ord("T")
    perms_block[9:12] = b"adb"
    perms_block[12:16] = os.urandom(4)
    perms_cipher = Cipher(algorithms.AES(file_key), modes.ECB()).encryptor()
    perms_value = perms_cipher.update(bytes(perms_block)) + perms_cipher.finalize()

    enc = PDEncryption()
    enc.set_filter("Standard")
    enc.set_v(5)
    enc.set_revision(5)
    enc.set_length(256)
    enc.set_p(permissions)
    enc.set_o(o_value)
    enc.set_u(u_value)
    enc.set_oe(oe)
    enc.set_ue(ue)
    enc.set_perms(perms_value)
    return handler, enc, password, file_key


def test_r5_read_path_recovers_file_key() -> None:
    """R5 deprecated Adobe Extension Level 3 path — pure read parity.

    The standard policy upgrades r5 → r6 on save (PDF 32000-2 §7.6.4
    "Algorithms 2.A and 2.B"), so the only way to exercise the r5 *read*
    branch is to hand-build a valid r5 ``/Encrypt`` and assert
    :meth:`prepare_for_decryption` recovers the same file key.
    """
    handler, enc, password, file_key = _build_r5_dictionary_via_handler()

    from pypdfbox.pdmodel.encryption.standard_security_handler import (
        StandardDecryptionMaterial,
    )

    reader = StandardSecurityHandler()
    reader.prepare_for_decryption(
        enc, b"\x00" * 16, StandardDecryptionMaterial(password)
    )
    assert reader.get_encryption_key() == file_key
    ap = reader.get_current_access_permission()
    assert ap is not None
    # In this synthetic dict the same password materialises both the owner
    # and user hash slots — the handler authenticates as owner first
    # (matching upstream ``prepareForDecryption`` order), so we expect the
    # owner-level access permission rather than the read-only user mask.
    assert ap.is_owner_permission() is True
    # Sanity — the original handler is unchanged.
    assert handler.get_revision() == 5


def test_r5_wrong_password_rejected() -> None:
    _, enc, _password, _file_key = _build_r5_dictionary_via_handler()
    from pypdfbox.pdmodel.encryption.standard_security_handler import (
        StandardDecryptionMaterial,
    )

    reader = StandardSecurityHandler()
    with pytest.raises(InvalidPasswordException):
        reader.prepare_for_decryption(
            enc, b"\x00" * 16, StandardDecryptionMaterial(b"wrong-pw")
        )


# --------------------------------------------- /EncryptMetadata=False round-trip


@pytest.mark.parametrize(
    ("label", "key_length", "prefer_aes"),
    [
        ("r3-rc4-128", 128, False),
        ("r4-aes-128", 128, True),
        ("r6-aes-256", 256, False),
    ],
    ids=["r3", "r4", "r6"],
)
def test_encrypt_metadata_false_round_trip(
    label: str, key_length: int, prefer_aes: bool
) -> None:
    """``/EncryptMetadata=false`` round-trip — cleartext metadata + encrypted
    payload — for every revision that surfaces the flag.

    Wave 1367 latent-bug fix: :class:`StandardProtectionPolicy` now exposes
    ``set_encrypt_metadata`` and the standard security handler propagates
    the flag into the on-the-wire ``PDEncryption``. The writer + COSStream
    decrypt-pass attach hook also learn to skip ``/Type /Metadata`` streams
    when the active handler reports ``is_encrypt_metadata() == False``, so
    external indexers see cleartext while the rest of the document stays
    enciphered. This test exercises the entire path end-to-end.
    """
    pd, payload = _build_document()
    policy = StandardProtectionPolicy(
        owner_password="ownerMD",
        user_password="userMD",
        permissions=AccessPermission(),
    )
    policy.set_encryption_key_length(key_length)
    policy.set_prefer_aes(prefer_aes)
    policy.set_encrypt_metadata(False)
    pd.protect(policy)
    sink = io.BytesIO()
    pd.save(sink)
    saved = sink.getvalue()
    pd.close()

    # Content stream is enciphered.
    assert _CONTENT_PAYLOAD not in saved, (
        f"{label}: cleartext content leaked into saved bytes"
    )
    # /Metadata stream stays cleartext on disk — the whole point of the
    # /EncryptMetadata false flag (external indexers / library catalogs
    # need to read /Metadata without the password).
    assert _METADATA_XML in saved, (
        f"{label}: /Metadata stream should be cleartext on disk"
    )

    with PDDocument.load(saved, password="userMD") as reloaded:
        enc = reloaded.get_encryption()
        assert enc is not None
        assert enc.is_encrypt_meta_data() is False
        assert _first_page_contents(reloaded) == payload
        assert _catalog_metadata_bytes(reloaded) == _METADATA_XML


# -------------------------------- PublicKeySecurityHandler envelope variations


def _build_self_signed_rsa() -> tuple[object, object]:
    """Return ``(cert, private_key)`` — same shape as the wave-1289 helper."""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, "wave1367-recipient")]
    )
    not_before = datetime.datetime(2020, 1, 1)
    not_after = datetime.datetime(2040, 1, 1)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(not_before)
        .not_valid_after(not_after)
        .sign(private_key, hashes.SHA256())
    )
    return cert, private_key


class _StubDocument:
    """Captures ``set_encryption_dictionary`` calls."""

    def __init__(self) -> None:
        self.encryption: object | None = None

    def set_encryption_dictionary(self, encryption: object) -> None:
        self.encryption = encryption


@pytest.mark.parametrize(
    "key_length",
    [128, 256],
    ids=["pubkey-128", "pubkey-256"],
)
def test_public_key_single_recipient_round_trip_per_key_length(
    key_length: int,
) -> None:
    """One recipient, both supported key lengths (128 = r4 AESV2, 256 = r6 AESV3).

    Pins the read-side file-key recovery for each supported V=4 / V=5
    public-key configuration — the per-recipient-algo wave-1289 tests pin
    grouping but only at the default 128-bit key length.
    """
    try:
        cert, private_key = _build_self_signed_rsa()
    except Exception:  # noqa: BLE001
        pytest.skip("cert generation too heavy in this environment")

    recipient = PublicKeyRecipient(
        certificate=cert, permissions=AccessPermission()
    )
    policy = PublicKeyProtectionPolicy()
    policy.add_recipient(recipient)
    policy.set_encryption_key_length(key_length)

    handler = PublicKeySecurityHandler(protection_policy=policy)
    document = _StubDocument()
    handler.prepare_document(document)
    expected_key = handler.get_encryption_key()
    assert expected_key is not None
    assert len(expected_key) == key_length // 8

    encryption = document.encryption
    assert encryption is not None
    material = PublicKeyDecryptionMaterial(
        certificate=cert, private_key=private_key
    )
    decrypt = PublicKeySecurityHandler()
    decrypt.prepare_for_decryption(encryption, b"\x00" * 16, material)
    assert decrypt.get_encryption_key() == expected_key


def test_public_key_recipient_with_mismatched_key_cannot_decrypt() -> None:
    """A recipient whose private key was *not* in the policy's recipient
    set must fail to recover the file key — pins the negative case for
    envelope-recipient pairing."""
    try:
        cert_a, _key_a = _build_self_signed_rsa()
        _cert_b, key_b_other = _build_self_signed_rsa()
    except Exception:  # noqa: BLE001
        pytest.skip("cert generation too heavy in this environment")

    policy = PublicKeyProtectionPolicy()
    policy.add_recipient(
        PublicKeyRecipient(certificate=cert_a, permissions=AccessPermission())
    )
    policy.set_encryption_key_length(128)

    handler = PublicKeySecurityHandler(protection_policy=policy)
    document = _StubDocument()
    handler.prepare_document(document)
    encryption = document.encryption
    assert encryption is not None

    # Try to decrypt with the other recipient's key — must NOT match.
    # The handler surfaces failures as IOError / OSError / ValueError
    # depending on which step rejects the mismatch (PKCS#7 recipient lookup
    # vs. AES key-unwrap vs. seed-recovery hash compare). All inherit from
    # ``Exception`` so widening the catch keeps the test resilient against
    # later refactors of the error taxonomy.
    material = PublicKeyDecryptionMaterial(
        certificate=cert_a, private_key=key_b_other
    )
    decrypt = PublicKeySecurityHandler()
    with pytest.raises((OSError, ValueError)):
        decrypt.prepare_for_decryption(encryption, b"\x00" * 16, material)


def test_public_key_four_recipients_two_distinct_masks_yield_two_envelopes() -> None:
    """Four-recipient extension of the three-recipient wave-1289 case — pins
    that the per-mask collapsing scales beyond pairs."""
    try:
        perms_locked = AccessPermission()
        perms_locked.set_can_print(False)
        perms_open = AccessPermission()
        cert_keys: list[tuple[object, object]] = [
            _build_self_signed_rsa() for _ in range(4)
        ]
    except Exception:  # noqa: BLE001
        pytest.skip("cert generation too heavy in this environment")

    policy = PublicKeyProtectionPolicy()
    for idx, (cert, _key) in enumerate(cert_keys):
        perm = perms_locked if idx < 2 else perms_open
        policy.add_recipient(
            PublicKeyRecipient(certificate=cert, permissions=perm)
        )
    policy.set_encryption_key_length(128)

    handler = PublicKeySecurityHandler(protection_policy=policy)
    document = _StubDocument()
    handler.prepare_document(document)
    encryption = document.encryption
    assert encryption is not None
    # V>=4 crypt-filter handler keeps /Recipients inside /CF /DefaultCryptFilter.
    default_cf = encryption.get_default_crypt_filter_dictionary()
    assert default_cf is not None
    recipients = default_cf.get_recipients()
    assert recipients is not None
    # Two distinct masks → exactly two envelopes regardless of recipient count.
    assert recipients.size() == 2

    expected_key = handler.get_encryption_key()
    assert expected_key is not None
    # All four recipients must round-trip the file key with their own keys.
    for cert, private_key in cert_keys:
        material = PublicKeyDecryptionMaterial(
            certificate=cert, private_key=private_key
        )
        decrypt = PublicKeySecurityHandler()
        decrypt.prepare_for_decryption(encryption, b"\x00" * 16, material)
        assert decrypt.get_encryption_key() == expected_key
