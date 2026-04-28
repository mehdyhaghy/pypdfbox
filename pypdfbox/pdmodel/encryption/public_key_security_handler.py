"""Public-key security handler.

Mirrors ``org.apache.pdfbox.pdmodel.encryption.PublicKeySecurityHandler``.

Decrypt path walks the ``/Recipients`` CMS-enveloped blobs on an
``/Encrypt`` dictionary, decrypts the first one that matches the supplied
private key (via ``cryptography.hazmat.primitives.serialization.pkcs7``),
and derives the file-encryption key per PDF 32000-1 §7.6.5.

Encrypt path generates a 20-byte seed, builds a one-recipient PKCS#7
envelope per ``PublicKeyRecipient`` using
``cryptography.hazmat.primitives.serialization.pkcs7.PKCS7EnvelopeBuilder``,
populates ``/Encrypt`` (`/Filter /Adobe.PubSec`, `/SubFilter`, `/V`, `/R`,
`/Length`, `/Recipients`, `/CF /DefaultCryptFilter`, `/StmF`, `/StrF`),
and derives the same SHA-1/SHA-256-truncated file key the decrypt path
expects.
"""

from __future__ import annotations

import hashlib
import os
from typing import TYPE_CHECKING

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.ciphers import algorithms
from cryptography.hazmat.primitives.serialization import pkcs7

from pypdfbox.cos import COSArray, COSString

from .access_permission import AccessPermission
from .pd_crypt_filter_dictionary import PDCryptFilterDictionary
from .security_handler import SecurityHandler

if TYPE_CHECKING:
    from .pd_encryption import PDEncryption
    from .public_key_decryption_material import PublicKeyDecryptionMaterial


# Per PDF 32000-1 §7.6.5: the seed prefix length for public-key key derivation.
_SEED_LENGTH = 20


class PublicKeySecurityHandler(SecurityHandler):
    """Lite port — both decrypt and encrypt paths wired.

    Decrypt validates a recipient envelope against the supplied private key
    and derives the file key per §7.6.5. Encrypt builds one PKCS#7 envelope
    per recipient and writes the matching `/Encrypt` dictionary.
    """

    FILTER: str = "Adobe.PubSec"

    SUBFILTER4: str = "adbe.pkcs7.s4"
    SUBFILTER5: str = "adbe.pkcs7.s5"

    def __init__(self, protection_policy: object | None = None) -> None:
        super().__init__()
        # Mirrors ``StandardSecurityHandler`` — write callers attach the
        # policy here so :meth:`prepare_document` can pull recipients +
        # key-length without an extra plumbing step.
        self._protection_policy = protection_policy

    # ------------------------------------------------------------ decrypt

    def prepare_for_decryption(
        self,
        encryption: PDEncryption,
        document_id: bytes,  # noqa: ARG002 — kept for API parity (unused for pubsec)
        decryption_material: object,
    ) -> None:
        """Locate the recipient envelope addressed to ``decryption_material``,
        decrypt it, and derive the file-encryption key.

        The PDF 32000-1 §7.6.5 derivation is:
          1. The CMS envelope decrypts to ``seed (20 bytes) || perms (4 bytes)``.
          2. Concatenate ``seed`` with every recipient blob (in order) and,
             when ``EncryptMetadata`` is false, four 0xFF bytes.
          3. Hash the concatenation — SHA-1 for V=4, SHA-256 for V=5 — and
             truncate to the configured key length in bytes.
        """
        # Local import to avoid a hard cycle at module load.
        from .public_key_decryption_material import PublicKeyDecryptionMaterial  # noqa: PLC0415

        if not isinstance(decryption_material, PublicKeyDecryptionMaterial):
            raise TypeError(
                "prepare_for_decryption expects PublicKeyDecryptionMaterial, "
                f"got {type(decryption_material).__name__}"
            )

        # Stash the material on the base so callers (e.g. PDDocument) can
        # query it back from the handler — mirrors upstream's
        # ``SecurityHandler#setDecryptionMaterial`` invocation at the top of
        # ``prepareForDecryption``.
        self.set_decryption_material(decryption_material)

        cert = decryption_material.get_certificate()
        private_key = decryption_material.get_private_key()
        if cert is None or private_key is None:
            raise ValueError(
                "PublicKeyDecryptionMaterial is missing a certificate or private key"
            )

        recipients_array = encryption.get_recipients()
        if recipients_array is None or recipients_array.size() == 0:
            raise ValueError("/Recipients array missing or empty on /Encrypt dictionary")

        # Snapshot the recipient blobs in their array order — needed both for
        # the per-recipient decrypt attempt and the eventual hash composition.
        recipient_blobs: list[bytes] = []
        for i in range(recipients_array.size()):
            entry = recipients_array.get_object(i)
            if not isinstance(entry, COSString):
                raise ValueError(
                    f"/Recipients[{i}] is not a COSString (got {type(entry).__name__})"
                )
            recipient_blobs.append(entry.get_bytes())

        envelope_plaintext: bytes | None = None
        for blob in recipient_blobs:
            try:
                envelope_plaintext = pkcs7.pkcs7_decrypt_der(
                    blob, cert, private_key, options=[]
                )
            except Exception:  # noqa: BLE001 — try every recipient before giving up
                continue
            if envelope_plaintext is not None:
                break

        if envelope_plaintext is None:
            raise ValueError(
                "Supplied private key matched none of the /Recipients envelopes"
            )

        if len(envelope_plaintext) < _SEED_LENGTH:
            raise ValueError(
                "Decrypted recipient envelope shorter than the 20-byte seed"
            )
        seed = envelope_plaintext[:_SEED_LENGTH]

        # Per PDF 32000-1 §7.6.5: the four bytes after the seed encode the
        # access permissions for the recipient who owns this envelope, as a
        # big-endian two's-complement int. Decode and propagate to the base
        # so callers (PDDocument.get_current_access_permission) see the
        # right surface, mirroring upstream behaviour.
        if len(envelope_plaintext) >= _SEED_LENGTH + 4:
            perms_unsigned = int.from_bytes(
                envelope_plaintext[_SEED_LENGTH : _SEED_LENGTH + 4], "big"
            )
            # Convert big-endian unsigned -> two's-complement signed.
            if perms_unsigned & 0x80000000:
                perms_signed = perms_unsigned - 0x1_0000_0000
            else:
                perms_signed = perms_unsigned
            self.set_current_access_permission(AccessPermission(perms_signed))

        version = encryption.get_v()
        revision = encryption.get_revision()
        key_length_bits = encryption.get_length() or 128
        key_length_bytes = key_length_bits // 8

        # Hash composition — see §7.6.5: seed || every recipient blob in order
        # || (when metadata is *not* encrypted) four 0xFF bytes.
        if version >= 5:
            digest = hashlib.sha256()
        else:
            digest = hashlib.sha1(usedforsecurity=False)
        digest.update(seed)
        for blob in recipient_blobs:
            digest.update(blob)
        if not encryption.is_encrypt_meta_data():
            digest.update(b"\xff\xff\xff\xff")
        encryption_key = digest.digest()[:key_length_bytes]

        self.set_encryption_key(encryption_key)
        self.set_key_length(key_length_bits)
        self.set_version(version)
        self.set_revision(revision)
        # Public-key handler always pairs with a crypt filter; AES is the
        # common case for V>=4 and required for V=5.
        self.set_aes(version >= 4)

    # ------------------------------------------------------------ encrypt

    def prepare_document(self, document: object) -> None:
        """Populate ``/Encrypt`` from the attached ``PublicKeyProtectionPolicy``.

        Per PDF 32000-1 §7.6.5:

        1. Generate a 20-byte cryptographically random seed.
        2. For each recipient, build a per-recipient blob = seed (20 bytes) ||
           permissions (4 bytes, big-endian) and wrap it in a one-recipient
           PKCS#7 envelope using AES-128 (V=4) or AES-256 (V=5) content
           encryption. The envelope is serialised as DER bytes.
        3. Stash the envelopes on ``/Encrypt /Recipients`` and write the
           companion fields ``/Filter``, ``/SubFilter``, ``/V``, ``/R``,
           ``/Length``, ``/CF /DefaultCryptFilter``, ``/StmF``, ``/StrF``.
        4. Derive the file-encryption key as
           ``hash(seed || every recipient blob in order
                  [|| 0xFF*4 if not encrypting metadata])``
           truncated to ``/Length // 8`` bytes — SHA-256 for V>=5, SHA-1 for
           V=4 — and seed ``self._encryption_key`` so the per-object cipher
           dispatch in :class:`SecurityHandler` works straight away.
        """
        # Late imports keep the public-key cluster's heavy dependencies out
        # of the module-load path for callers that only use the standard
        # handler.
        from .pd_encryption import PDEncryption  # noqa: PLC0415
        from .public_key_protection_policy import (  # noqa: PLC0415
            PublicKeyProtectionPolicy,
        )

        policy = getattr(self, "_protection_policy", None)
        if policy is None:
            # Fall back to scanning the document for an attached policy when
            # the handler was instantiated without one — mirrors how upstream
            # PDFBox finds the policy via the document's encryption setup.
            policy = getattr(document, "_protection_policy", None)
        if not isinstance(policy, PublicKeyProtectionPolicy):
            raise ValueError(
                "PublicKeySecurityHandler.prepare_document requires a "
                "PublicKeyProtectionPolicy"
            )

        recipients = policy.get_recipients()
        if not recipients:
            raise ValueError(
                "PublicKeyProtectionPolicy must have at least one recipient"
            )

        key_length_bits = policy.get_encryption_key_length() or 128
        # Pick V/R/CFM by key length. The spec only defines AES-128 (V=4) and
        # AES-256 (V=5) for /Adobe.PubSec; legacy RC4 variants are out of
        # scope for the lite port.
        if key_length_bits >= 256:
            key_length_bits = 256
            version = 5
            revision = 5
            sub_filter = self.SUBFILTER5
            cfm = PDCryptFilterDictionary.CFM_AESV3
            content_alg = algorithms.AES256
            digest_factory = hashlib.sha256
        else:
            key_length_bits = 128
            version = 4
            revision = 4
            sub_filter = self.SUBFILTER4
            cfm = PDCryptFilterDictionary.CFM_AESV2
            content_alg = algorithms.AES128
            digest_factory = hashlib.sha1

        seed = os.urandom(_SEED_LENGTH)

        envelopes: list[bytes] = []
        for recipient in recipients:
            cert = recipient.get_x509()
            if cert is None:
                raise ValueError(
                    "PublicKeyRecipient is missing its X.509 certificate"
                )
            permission_obj = recipient.get_permission()
            if permission_obj is None:
                raise ValueError(
                    "PublicKeyRecipient is missing its AccessPermission"
                )
            # Permissions are stored as a 4-byte two's-complement big-endian
            # integer per §7.6.5 — same on-the-wire shape upstream uses.
            perms_int = (
                permission_obj.get_permission_bytes() & 0xFFFFFFFF
            )
            blob = seed + perms_int.to_bytes(4, "big")

            builder = pkcs7.PKCS7EnvelopeBuilder()
            builder = builder.set_data(blob)
            builder = builder.add_recipient(cert)
            builder = builder.set_content_encryption_algorithm(content_alg)
            envelope_der = builder.encrypt(
                serialization.Encoding.DER,
                [pkcs7.PKCS7Options.Binary],
            )
            envelopes.append(envelope_der)

        # Build the /Encrypt dictionary.
        encryption = PDEncryption()
        encryption.set_filter(self.FILTER)
        encryption.set_sub_filter(sub_filter)
        encryption.set_v(version)
        encryption.set_revision(revision)
        encryption.set_length(key_length_bits)

        recipients_array = COSArray()
        for envelope_der in envelopes:
            recipients_array.add(COSString(envelope_der))
        # PDEncryption has no /Recipients setter — write through the COS
        # dictionary directly. The accessor side already accepts any
        # COSArray via get_recipients().
        encryption.get_cos_object().set_item("Recipients", recipients_array)

        crypt_filter = PDCryptFilterDictionary()
        crypt_filter.set_cfm(cfm)
        # /CF /Length is in bytes per Table 25 (note the bits/bytes split).
        crypt_filter.set_length(key_length_bits // 8)
        encryption.set_default_crypt_filter_dictionary(crypt_filter)
        encryption.set_stm_f("DefaultCryptFilter")
        encryption.set_str_f("DefaultCryptFilter")

        # Derive the file-encryption key per §7.6.5: hash(seed || every
        # recipient blob in order || (0xFF*4 when EncryptMetadata is false))
        # truncated to /Length // 8 bytes.
        digest = digest_factory(usedforsecurity=False) if version < 5 else digest_factory()
        digest.update(seed)
        for envelope_der in envelopes:
            digest.update(envelope_der)
        if not encryption.is_encrypt_meta_data():
            digest.update(b"\xff\xff\xff\xff")
        encryption_key = digest.digest()[: key_length_bits // 8]

        self.set_encryption_key(encryption_key)
        self.set_key_length(key_length_bits)
        self.set_version(version)
        self.set_revision(revision)
        # /Adobe.PubSec always pairs with AES in this lite port.
        self.set_aes(True)

        # Attach the encryption dictionary to the document if it exposes the
        # standard PDFBox setter (mirrors StandardSecurityHandler.prepare_document).
        if hasattr(document, "set_encryption_dictionary"):
            document.set_encryption_dictionary(encryption)

    # ------------------------------------------------------------ helpers

    @staticmethod
    def _coerce_recipients(value: object) -> COSArray | None:
        # Defensive accessor — currently unused but mirrors the upstream
        # tolerance for either array form.
        if isinstance(value, COSArray):
            return value
        return None

    # ------------------------------------------------------- upstream aliases
    #
    # These accessors mirror the surface that upstream's
    # ``PublicKeySecurityHandler`` (and its ``SecurityHandler<T_POLICY>``
    # base) exposes. They route to the existing internals so behavior stays
    # in lock-step with :meth:`prepare_document` and
    # :meth:`prepare_for_decryption`.

    def get_protection_policy(self) -> object | None:
        """Return the attached :class:`PublicKeyProtectionPolicy`, or ``None``.

        Mirrors ``SecurityHandler#getProtectionPolicy`` upstream.
        """
        return self._protection_policy

    def set_protection_policy(self, policy: object) -> None:
        """Attach a :class:`PublicKeyProtectionPolicy` to this handler.

        Mirrors ``SecurityHandler#setProtectionPolicy`` upstream.
        """
        self._protection_policy = policy

    def has_protection_policy(self) -> bool:
        """Whether a protection policy is attached.

        Mirrors ``SecurityHandler#hasProtectionPolicy`` upstream.
        """
        return self._protection_policy is not None

    def get_recipients(self) -> list:
        """Return the recipient list pulled from the attached policy.

        When no policy is attached, returns an empty list — matches the
        empty-iterator behaviour upstream callers see before
        :meth:`prepare_document` runs.
        """
        from .public_key_protection_policy import (  # noqa: PLC0415
            PublicKeyProtectionPolicy,
        )

        policy = self._protection_policy
        if isinstance(policy, PublicKeyProtectionPolicy):
            return policy.get_recipients()
        return []

    def add_recipient(self, recipient: object) -> None:
        """Append ``recipient`` to the attached policy's recipient list.

        Lazily instantiates a :class:`PublicKeyProtectionPolicy` if one
        isn't attached yet so callers can build up the policy fluently
        before invoking :meth:`prepare_document`.
        """
        from .public_key_protection_policy import (  # noqa: PLC0415
            PublicKeyProtectionPolicy,
        )

        policy = self._protection_policy
        if not isinstance(policy, PublicKeyProtectionPolicy):
            policy = PublicKeyProtectionPolicy()
            self._protection_policy = policy
        policy.add_recipient(recipient)  # type: ignore[arg-type]

    def compute_seed_value(self) -> bytes:
        """Return a fresh 20-byte seed per PDF 32000-1 §7.6.5.

        Placeholder helper — :meth:`prepare_document` generates its own
        seed inline; this alias exposes the same primitive for callers
        that need the seed independently (e.g. parity tests).
        """
        return os.urandom(_SEED_LENGTH)

    def derive_file_key(
        self,
        seed: bytes,
        recipient_blobs: list[bytes],
        version: int,
        key_length_bits: int,
        encrypt_metadata: bool = True,
    ) -> bytes:
        """Derive the file-encryption key per PDF 32000-1 §7.6.5.

        Hash composition:
          ``hash(seed || every recipient blob in order
                 [|| 0xFF*4 if not encrypt_metadata])``

        SHA-256 for V>=5, SHA-1 (non-security context) otherwise. The
        result is truncated to ``key_length_bits // 8`` bytes.
        """
        if version >= 5:
            digest = hashlib.sha256()
        else:
            digest = hashlib.sha1(usedforsecurity=False)
        digest.update(seed)
        for blob in recipient_blobs:
            digest.update(blob)
        if not encrypt_metadata:
            digest.update(b"\xff\xff\xff\xff")
        return digest.digest()[: key_length_bits // 8]


__all__ = ["PublicKeySecurityHandler"]
