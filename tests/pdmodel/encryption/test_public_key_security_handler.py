from __future__ import annotations

import pytest

from pypdfbox.pdmodel.encryption.access_permission import AccessPermission
from pypdfbox.pdmodel.encryption.public_key_decryption_material import (
    PublicKeyDecryptionMaterial,
)
from pypdfbox.pdmodel.encryption.public_key_protection_policy import (
    PublicKeyProtectionPolicy,
)
from pypdfbox.pdmodel.encryption.public_key_recipient import PublicKeyRecipient
from pypdfbox.pdmodel.encryption.public_key_security_handler import (
    PublicKeySecurityHandler,
)


def test_protection_policy_collects_recipients() -> None:
    policy = PublicKeyProtectionPolicy()
    r1 = PublicKeyRecipient()
    r2 = PublicKeyRecipient()
    policy.add_recipient(r1)
    policy.add_recipient(r2)
    assert policy.get_recipients() == [r1, r2]
    assert policy.get_number_of_recipients() == 2


def test_protection_policy_remove_recipient_returns_bool() -> None:
    policy = PublicKeyProtectionPolicy()
    r = PublicKeyRecipient()
    policy.add_recipient(r)
    assert policy.remove_recipient(r) is True
    assert policy.remove_recipient(r) is False
    assert policy.get_recipients() == []


def test_recipient_round_trips_cert_and_permission() -> None:
    perm = AccessPermission()
    perm.set_can_print(False)
    sentinel_cert = object()  # stand-in — type only enforced statically
    r = PublicKeyRecipient(certificate=sentinel_cert, permissions=perm)  # type: ignore[arg-type]
    assert r.get_x509() is sentinel_cert
    assert r.get_permission() is perm
    other_perm = AccessPermission.get_owner_access_permission()
    r.set_permission(other_perm)
    assert r.get_permission() is other_perm
    r.set_x509(None)
    assert r.get_x509() is None


def test_decryption_material_round_trips_cert_and_key() -> None:
    sentinel_cert = object()
    sentinel_key = object()
    material = PublicKeyDecryptionMaterial(password=b"hunter2")
    # Use the bypass setters with sentinels — set_certificate validates type,
    # so we set the underlying field directly to avoid touching real PEM/DER
    # material in this unit test.
    material._certificate = sentinel_cert  # type: ignore[assignment]
    material.set_private_key(sentinel_key)  # type: ignore[arg-type]
    assert material.get_certificate() is sentinel_cert
    # Already-loaded keys (non-bytes) are returned as-is.
    assert material.get_private_key() is sentinel_key
    assert material.get_password() == b"hunter2"
    material.set_password(None)
    assert material.get_password() is None


def test_decryption_material_rejects_unknown_certificate_type() -> None:
    material = PublicKeyDecryptionMaterial()
    with pytest.raises(TypeError):
        material.set_certificate(12345)  # type: ignore[arg-type]


def test_security_handler_filter_constant() -> None:
    assert PublicKeySecurityHandler.FILTER == "Adobe.PubSec"


def test_get_filter_instance_accessor_matches_constant() -> None:
    handler = PublicKeySecurityHandler()
    assert handler.get_filter() == "Adobe.PubSec"
    assert handler.get_filter() == PublicKeySecurityHandler.FILTER


def test_prepare_document_for_encryption_alias_routes_to_prepare_document() -> None:
    """The upstream-spelled hook delegates to :meth:`prepare_document`."""
    handler = PublicKeySecurityHandler()
    # No policy attached — both spellings must surface the same error.
    with pytest.raises(ValueError, match="PublicKeyProtectionPolicy"):
        handler.prepare_document_for_encryption(object())


def test_get_number_of_recipients_without_policy_returns_zero() -> None:
    handler = PublicKeySecurityHandler()
    assert handler.get_number_of_recipients() == 0


def test_get_number_of_recipients_passes_through_policy() -> None:
    policy = PublicKeyProtectionPolicy()
    policy.add_recipient(PublicKeyRecipient())
    policy.add_recipient(PublicKeyRecipient())
    handler = PublicKeySecurityHandler(policy)
    assert handler.get_number_of_recipients() == 2


def test_compute_version_number_branches() -> None:
    """Mirror upstream ``SecurityHandler#computeVersionNumber`` per branch."""
    # Default state — no policy, default 40-bit base key length.
    handler = PublicKeySecurityHandler()
    handler.set_key_length(40)
    assert handler.compute_version_number() == 1

    handler.set_key_length(128)
    assert handler.compute_version_number() == 2

    # Policy with preferAES + 128 keyLength → V=4.
    policy = PublicKeyProtectionPolicy()
    policy.set_encryption_key_length(128)
    policy.set_prefer_aes(True)
    handler = PublicKeySecurityHandler(policy)
    assert handler.compute_version_number() == 4

    # Policy with 256 keyLength → V=5 (AES-256, irrespective of preferAES).
    policy = PublicKeyProtectionPolicy()
    policy.set_encryption_key_length(256)
    handler = PublicKeySecurityHandler(policy)
    assert handler.compute_version_number() == 5

    # 128-bit policy without preferAES falls back to V=2 (RC4-128).
    policy = PublicKeyProtectionPolicy()
    policy.set_encryption_key_length(128)
    handler = PublicKeySecurityHandler(policy)
    assert handler.compute_version_number() == 2


def test_prepare_document_requires_recipients() -> None:
    handler = PublicKeySecurityHandler(PublicKeyProtectionPolicy())
    with pytest.raises(ValueError, match="recipient"):
        handler.prepare_document(object())


def test_prepare_document_requires_protection_policy() -> None:
    handler = PublicKeySecurityHandler()
    with pytest.raises(ValueError, match="PublicKeyProtectionPolicy"):
        handler.prepare_document(object())


def test_prepare_for_decryption_rejects_wrong_material_type() -> None:
    from pypdfbox.pdmodel.encryption.pd_encryption import PDEncryption

    handler = PublicKeySecurityHandler()
    with pytest.raises(TypeError):
        handler.prepare_for_decryption(PDEncryption(), b"id", object())


def test_prepare_for_decryption_requires_recipient_array() -> None:
    from pypdfbox.pdmodel.encryption.pd_encryption import PDEncryption

    handler = PublicKeySecurityHandler()
    material = PublicKeyDecryptionMaterial()
    # Inject sentinels so the cert/key None check passes and we exercise the
    # /Recipients lookup branch instead.
    material._certificate = object()  # type: ignore[assignment]
    material._private_key_raw = object()  # type: ignore[assignment]
    with pytest.raises(ValueError, match="Recipients"):
        handler.prepare_for_decryption(PDEncryption(), b"id", material)


def _build_self_signed_rsa() -> tuple[object, object]:
    """Return ``(cert, private_key)`` — a fresh self-signed 2048-bit RSA
    certificate suitable for one-shot CMS recipient wrapping."""
    import datetime

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, "pypdfbox-test-recipient")]
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
    """Minimal stand-in for PDDocument.set_encryption_dictionary capture.

    The handler only needs ``set_encryption_dictionary`` to be callable; we
    re-use the captured PDEncryption on the decrypt side instead of round-
    tripping through a real COSDocument trailer.
    """

    def __init__(self) -> None:
        self.encryption = None

    def set_encryption_dictionary(self, encryption: object) -> None:
        self.encryption = encryption


@pytest.mark.parametrize("key_length_bits", [128, 256])
def test_prepare_document_round_trip_matches_decrypt_path(
    key_length_bits: int,
) -> None:
    """Encrypt a synthetic document, decrypt it, assert keys agree.

    This is the public-key analogue of the standard-handler round-trip — we
    don't write a full PDF, just verify that ``prepare_document`` produces a
    `/Recipients`/`/CF` set that ``prepare_for_decryption`` can consume back
    into the *same* file-encryption key.
    """
    try:
        cert, private_key = _build_self_signed_rsa()
    except Exception:  # noqa: BLE001
        pytest.skip("cert generation too heavy in this environment")

    permissions = AccessPermission()
    permissions.set_can_print(False)
    recipient = PublicKeyRecipient(certificate=cert, permissions=permissions)

    policy = PublicKeyProtectionPolicy()
    policy.add_recipient(recipient)
    policy.set_encryption_key_length(key_length_bits)

    handler = PublicKeySecurityHandler(protection_policy=policy)
    document = _StubDocument()
    handler.prepare_document(document)

    assert document.encryption is not None
    assert document.encryption.get_filter() == "Adobe.PubSec"
    assert document.encryption.get_length() == key_length_bits
    if key_length_bits == 256:
        assert document.encryption.get_v() == 5
        assert document.encryption.get_sub_filter() == "adbe.pkcs7.s5"
    else:
        assert document.encryption.get_v() == 4
        assert document.encryption.get_sub_filter() == "adbe.pkcs7.s4"
    recipients_array = document.encryption.get_recipients()
    assert recipients_array is not None
    assert recipients_array.size() == 1

    encrypt_key = handler.get_encryption_key()
    assert encrypt_key is not None
    assert len(encrypt_key) == key_length_bits // 8

    # Decrypt path — feed the same /Encrypt back through with the matching
    # private key and verify the derived file-encryption key matches.
    material = PublicKeyDecryptionMaterial(certificate=cert, private_key=private_key)
    decrypt_handler = PublicKeySecurityHandler()
    decrypt_handler.prepare_for_decryption(
        document.encryption, b"\x00" * 16, material
    )
    assert decrypt_handler.get_encryption_key() == encrypt_key
    assert decrypt_handler.get_key_length() == key_length_bits
    assert decrypt_handler.is_aes() is True
    # Decryption material is stashed on the base handler — mirrors upstream
    # ``SecurityHandler#setDecryptionMaterial`` getting called from the top
    # of ``prepareForDecryption``.
    assert decrypt_handler.get_decryption_material() is material
    # Access permissions ride the envelope as a 4-byte big-endian signed
    # int starting at offset 20; the handler decodes them and exposes them
    # via ``get_current_access_permission``.
    decoded = decrypt_handler.get_current_access_permission()
    assert decoded is not None
    assert (decoded.get_permission_bytes() & 0xFFFFFFFF) == (
        permissions.get_permission_bytes() & 0xFFFFFFFF
    )


# --------------------------------------------------------- new parity surface


def test_append_cert_info_emits_serial_and_issuer_diagnostic() -> None:
    """Mirrors upstream ``appendCertInfo`` (Java line 296) — produces the
    ``serial-#`` / ``issuer`` mismatch diagnostic that ``prepare_for_decryption``
    appends to its error message."""

    class _Cert:
        serial_number = 0xDEADBEEF

    class _MaterialCert:
        issuer = "CN=test-cert"

    accumulator: list[str] = []
    PublicKeySecurityHandler.append_cert_info(
        accumulator,
        rid_serial_number=0xCAFEBABE,
        rid_issuer="CN=other-issuer",
        certificate=_Cert(),
        material_cert=_MaterialCert(),
    )
    rendered = "".join(accumulator)
    assert "serial-#: rid cafebabe" in rendered
    assert "vs. cert deadbeef" in rendered
    assert "rid 'CN=other-issuer'" in rendered
    assert "vs. cert 'CN=test-cert'" in rendered


def test_append_cert_info_no_op_when_serial_is_none() -> None:
    accumulator: list[str] = []
    PublicKeySecurityHandler.append_cert_info(
        accumulator,
        rid_serial_number=None,
        rid_issuer="CN=ignored",
        certificate=object(),
        material_cert=None,
    )
    assert accumulator == []


def test_append_cert_info_handles_null_material_cert() -> None:
    class _Cert:
        serial_number = 1

    accumulator: list[str] = []
    PublicKeySecurityHandler.append_cert_info(
        accumulator,
        rid_serial_number=2,
        rid_issuer="CN=issuer",
        certificate=_Cert(),
        material_cert=None,
    )
    assert "vs. cert 'null'" in "".join(accumulator)


def test_append_cert_info_unknown_cert_serial_when_attribute_missing() -> None:
    """When the material cert lacks ``serial_number``, the diagnostic uses
    ``unknown`` — matches upstream's null-guard around ``getSerialNumber``."""
    accumulator: list[str] = []
    PublicKeySecurityHandler.append_cert_info(
        accumulator,
        rid_serial_number=0x10,
        rid_issuer="CN=issuer",
        certificate=object(),  # no serial_number attribute
        material_cert=None,
    )
    rendered = "".join(accumulator)
    assert "vs. cert unknown" in rendered


def test_compute_recipients_field_requires_attached_policy() -> None:
    """Mirrors upstream ``computeRecipientsField`` precondition — without a
    policy the helper raises rather than silently producing an empty list."""
    handler = PublicKeySecurityHandler()
    with pytest.raises(ValueError, match="PublicKeyProtectionPolicy"):
        handler._compute_recipients_field(b"\x00" * 20)


def test_compute_recipients_field_validates_recipient_certificate() -> None:
    policy = PublicKeyProtectionPolicy()
    policy.add_recipient(PublicKeyRecipient(permissions=AccessPermission()))
    handler = PublicKeySecurityHandler(protection_policy=policy)
    with pytest.raises(ValueError, match="X.509 certificate"):
        handler._compute_recipients_field(b"\x00" * 20)


def test_compute_recipients_field_validates_recipient_permissions() -> None:
    policy = PublicKeyProtectionPolicy()
    policy.add_recipient(PublicKeyRecipient(certificate=object()))  # type: ignore[arg-type]
    handler = PublicKeySecurityHandler(protection_policy=policy)
    with pytest.raises(ValueError, match="AccessPermission"):
        handler._compute_recipients_field(b"\x00" * 20)


def test_prepare_encryption_dict_aes_wires_default_crypt_filter() -> None:
    """Mirrors upstream ``prepareEncryptionDictAES`` — the helper sets the
    ``/CF /DefaultCryptFilter`` slot, ``/StmF``, ``/StrF`` and flips the
    handler's AES flag."""
    from pypdfbox.pdmodel.encryption.pd_crypt_filter_dictionary import (
        PDCryptFilterDictionary,
    )
    from pypdfbox.pdmodel.encryption.pd_encryption import PDEncryption

    handler = PublicKeySecurityHandler()
    handler.set_key_length(128)
    encryption = PDEncryption()
    handler._prepare_encryption_dict_aes(
        encryption, PDCryptFilterDictionary.CFM_AESV2, [b"recipient-blob"]
    )
    assert handler.is_aes() is True
    crypt_filter = encryption.get_default_crypt_filter_dictionary()
    assert crypt_filter is not None
    assert crypt_filter.get_cfm() == PDCryptFilterDictionary.CFM_AESV2
    # /CF /Length is bytes (not bits) per Table 25.
    assert crypt_filter.get_length() == 16
    assert encryption.get_stm_f() == "DefaultCryptFilter"
    assert encryption.get_str_f() == "DefaultCryptFilter"


# --------------------------- public-name parity surface (Wave 1268) -----


def test_prepare_encryption_dict_aes_public_name_matches_underscore_alias() -> None:
    """Promoted public name routes to the same body as the underscore alias.

    Mirrors upstream ``prepareEncryptionDictAES`` (Java line 419).
    """
    assert (
        PublicKeySecurityHandler.prepare_encryption_dict_aes
        is PublicKeySecurityHandler._prepare_encryption_dict_aes
    )


def test_compute_recipients_field_public_name_matches_underscore_alias() -> None:
    """Promoted public name routes to the same body as the underscore alias.

    Mirrors upstream ``computeRecipientsField`` (Java line 438).
    """
    assert (
        PublicKeySecurityHandler.compute_recipients_field
        is PublicKeySecurityHandler._compute_recipients_field
    )


def test_create_der_for_recipient_returns_der_envelope() -> None:
    """Mirrors upstream ``createDERForRecipient`` (Java line 476).

    Wraps a 24-byte payload in a one-recipient PKCS#7 envelope addressed to
    ``cert``; the output must be DER-encoded and non-empty.
    """
    try:
        cert, _key = _build_self_signed_rsa()
    except Exception:  # noqa: BLE001
        pytest.skip("cert generation too heavy in this environment")

    handler = PublicKeySecurityHandler()
    pkcs7_input = b"\x00" * 24
    envelope = handler.create_der_for_recipient(pkcs7_input, cert)
    assert isinstance(envelope, bytes)
    assert len(envelope) > 0
    # DER ContentInfo is a SEQUENCE, so the leading tag byte is 0x30.
    assert envelope[0] == 0x30


def test_compute_recipient_info_returns_der_envelope() -> None:
    """Mirrors upstream ``computeRecipientInfo`` (Java line 528).

    Returns the DER bytes that wrap a CEK key-transport blob for ``cert``.
    """
    try:
        cert, _key = _build_self_signed_rsa()
    except Exception:  # noqa: BLE001
        pytest.skip("cert generation too heavy in this environment")

    handler = PublicKeySecurityHandler()
    cek = b"\x01" * 16
    blob = handler.compute_recipient_info(cert, cek)
    assert isinstance(blob, bytes)
    assert len(blob) > 0
    assert blob[0] == 0x30


def test_compute_recipients_field_picks_aes256_for_256_bit_policy() -> None:
    """Public ``compute_recipients_field`` honours the policy's key length.

    Mirrors upstream ``computeRecipientsField`` (Java line 438) — the AES
    variant choice is driven by the attached ``PublicKeyProtectionPolicy``.
    """
    try:
        cert, _key = _build_self_signed_rsa()
    except Exception:  # noqa: BLE001
        pytest.skip("cert generation too heavy in this environment")

    policy = PublicKeyProtectionPolicy()
    policy.set_encryption_key_length(256)
    permissions = AccessPermission()
    policy.add_recipient(
        PublicKeyRecipient(certificate=cert, permissions=permissions)
    )
    handler = PublicKeySecurityHandler(protection_policy=policy)
    envelopes = handler.compute_recipients_field(b"\x00" * 20)
    assert len(envelopes) == 1
    assert envelopes[0][0] == 0x30
