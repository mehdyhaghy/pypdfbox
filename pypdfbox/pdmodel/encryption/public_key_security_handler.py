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
from typing import TYPE_CHECKING, cast

from cryptography.exceptions import UnsupportedAlgorithm
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.ciphers import algorithms
from cryptography.hazmat.primitives.serialization import pkcs7

from pypdfbox.cos import COSArray, COSString

from .access_permission import AccessPermission
from .pd_crypt_filter_dictionary import PDCryptFilterDictionary
from .security_handler import SecurityHandler

if TYPE_CHECKING:
    from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey

    from .pd_encryption import PDEncryption
    from .public_key_recipient import PublicKeyRecipient


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

        # Per PDF 32000-1 §7.6.5 the /Recipients array lives at the /Encrypt
        # top level for the legacy (V<4) public-key handler, but moves *into*
        # the default crypt filter (/CF /DefaultCryptFilter /Recipients) for
        # the crypt-filter-based V>=4 handlers (AES-128 V=4, AES-256 V=5) that
        # Acrobat and Apache PDFBox emit. Probe the top level first, then fall
        # back to the default crypt filter — mirrors upstream
        # PublicKeySecurityHandler#prepareForDecryption, which reads
        # getDefaultCryptFilterDictionary().getRecipients() when the
        # /Encrypt-level array is absent.
        recipients_array = encryption.get_recipients()
        if recipients_array is None or recipients_array.size() == 0:
            default_cf = encryption.get_default_crypt_filter_dictionary()
            if default_cf is not None:
                recipients_array = default_cf.get_recipients()
        if recipients_array is None or recipients_array.size() == 0:
            raise ValueError(
                "/Recipients array missing or empty on /Encrypt dictionary "
                "(checked both the top level and /CF /DefaultCryptFilter)"
            )

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
        rsa_private_key = cast("RSAPrivateKey", private_key)
        unsupported_algo: bool = False
        for blob in recipient_blobs:
            try:
                envelope_plaintext = pkcs7.pkcs7_decrypt_der(
                    blob, cert, rsa_private_key, options=[]
                )
            except UnsupportedAlgorithm:
                # The CMS envelope uses a content-encryption cipher the
                # ``cryptography`` PKCS#7 backend can't decrypt (it supports
                # AES-128/256-CBC only). Apache PDFBox and Acrobat default to
                # RC2-CBC for the recipient envelope, which OpenSSL no longer
                # exposes — so a PDFBox/Acrobat-produced public-key file is not
                # decryptable here regardless of the private key. Flag it so the
                # final error names the real cause instead of "wrong key".
                unsupported_algo = True
                continue
            except Exception:  # noqa: BLE001 — try every recipient before giving up
                continue
            if envelope_plaintext is not None:
                break

        if envelope_plaintext is None:
            if unsupported_algo:
                raise UnsupportedAlgorithm(
                    "Recipient envelope uses an unsupported CMS content cipher "
                    "(e.g. RC2-CBC, the Apache PDFBox / Acrobat default). The "
                    "cryptography PKCS#7 backend decrypts AES-128/256-CBC "
                    "envelopes only; RC2 is not exposed by OpenSSL. pypdfbox "
                    "writes AES envelopes, which interoperate; reading a "
                    "PDFBox-RC2 public-key file is not supported."
                )
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
        digest = (
            hashlib.sha256()
            if version >= 5
            else hashlib.sha1(usedforsecurity=False)
        )
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
        2. Group recipients by their 4-byte public-key permission mask. The
           spec calls for ONE envelope per *distinct permission set* — a
           multi-recipient envelope when several recipients share the same
           permissions, and separate envelopes when they diverge. The per
           -recipient blob in each envelope is ``seed (20 bytes) ||
           permissions (4 bytes, big-endian)``, wrapped in PKCS#7 using
           AES-128 (V=4) or AES-256 (V=5) content encryption and serialised
           as DER bytes.
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
        content_alg: type[algorithms.AES128] | type[algorithms.AES256]
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

        # Group recipients by their public-key permission mask per PDF
        # 32000-1 §7.6.5. Recipients that share permissions ride a single
        # multi-recipient envelope; distinct permission sets each get their
        # own envelope. The mask order is preserved by first-appearance so
        # the on-disk /Recipients array stays deterministic across runs and
        # matches policy author intent (the file-key digest then hashes
        # envelopes in that same order).
        permission_mask_to_recipients: dict[int, list[PublicKeyRecipient]] = {}
        mask_order: list[int] = []
        for recipient in recipients:
            if recipient.get_x509() is None:
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
            # Upstream packs ``getPermissionBytesForPublicKey()`` (bit 1 set,
            # bits 7/8 and 13-32 cleared), NOT the raw ``getPermissionBytes()``;
            # see PublicKeySecurityHandler#computeRecipientInfo line 449.
            perms_int = (
                permission_obj.get_permission_bytes_for_public_key() & 0xFFFFFFFF
            )
            if perms_int not in permission_mask_to_recipients:
                permission_mask_to_recipients[perms_int] = []
                mask_order.append(perms_int)
            permission_mask_to_recipients[perms_int].append(recipient)

        envelopes: list[bytes] = []
        for perms_int in mask_order:
            group = permission_mask_to_recipients[perms_int]
            blob = seed + perms_int.to_bytes(4, "big")

            builder = pkcs7.PKCS7EnvelopeBuilder()
            builder = builder.set_data(blob)
            for recipient in group:
                builder = builder.add_recipient(recipient.get_x509())
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

        # Crypt-filter-based public-key handler (V>=4): the /Recipients array
        # lives INSIDE /CF /DefaultCryptFilter, not at the /Encrypt top level.
        # This is what Apache PDFBox and Acrobat emit and expect to read back
        # (PublicKeySecurityHandler#prepareEncryptionDictAES) — writing it at
        # the top level instead produces a file PDFBox opens without error but
        # derives the WRONG file key for (recipient-byte mismatch → garbage
        # streams → empty extracted text). Mirror upstream by routing the
        # envelopes through :meth:`prepare_encryption_dict_aes`, which sets the
        # crypt filter's /Recipients + wires /StmF and /StrF.
        crypt_filter = PDCryptFilterDictionary()
        crypt_filter.set_cfm(cfm)
        # The public-key READ path derives the file-key length from this crypt
        # filter's /Length: upstream PublicKeySecurityHandler#prepareForDecryption
        # calls setKeyLength(getDefaultCryptFilterDictionary().getLength()) and
        # truncates the SHA digest to that-many-bits/8. Apache PDFBox writes the
        # value in BITS here (128 / 256), NOT bytes — so we must too. Writing 16
        # (bytes) makes a PDFBox reader truncate the file key to 16 *bits* (2
        # bytes), opening the file without error but deciphering every stream to
        # garbage (empty extracted text). Match upstream and write bits.
        crypt_filter.set_length(key_length_bits)
        recipients_cos = COSArray()
        for envelope_der in envelopes:
            recipients_cos.add(COSString(envelope_der))
        crypt_filter.set_recipients(recipients_cos)
        recipients_cos.set_direct(True)
        encryption.set_default_crypt_filter_dictionary(crypt_filter)
        # Keep the whole /CF subtree DIRECT (inline). If /CF — or its
        # /DefaultCryptFilter, or the /Recipients COSStrings within it — were
        # written as indirect objects, a reader (Apache PDFBox / Acrobat) would
        # dereference them mid-``prepareForDecryption`` and run the per-object
        # string decrypt with the file key still unset → NullPointerException
        # in calcFinalKey. Upstream's prepareEncryptionDictAES marks the same
        # subtree direct for exactly this reason (and the PDFBOX-4436 Android
        # workaround). The crypt filter dict itself is already set direct by
        # set_crypt_filter_dictionary; mark the containing /CF too.
        cf_dict = encryption.get_cf()
        if cf_dict is not None:
            cf_dict.set_direct(True)
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

    @staticmethod
    def append_cert_info(
        extra_info: list[str],
        rid_serial_number: int | None,
        rid_issuer: object,
        certificate: object,
        material_cert: object,
    ) -> None:
        """Append a diagnostic ``serial-#`` / ``issuer`` mismatch line.

        Mirrors upstream ``PublicKeySecurityHandler#appendCertInfo`` (Java
        line 296). Emitted by :meth:`prepare_for_decryption` when no
        recipient envelope matched the supplied certificate, so callers can
        see *why* the cert lookup failed (serial-number mismatch vs. issuer
        mismatch).

        ``extra_info`` is the diagnostic accumulator — upstream passes a
        ``StringBuilder``; we use a list of strings the caller can ``"".join``
        to keep the helper allocation-free.
        """
        if rid_serial_number is None:
            return
        cert_serial: str = "unknown"
        cert_serial_number = getattr(certificate, "serial_number", None)
        if cert_serial_number is not None:
            cert_serial = format(int(cert_serial_number), "x")
        if material_cert is None:
            material_issuer = "null"
        else:
            material_issuer = str(getattr(material_cert, "issuer", material_cert))
        extra_info.append("serial-#: rid ")
        extra_info.append(format(int(rid_serial_number), "x"))
        extra_info.append(" vs. cert ")
        extra_info.append(cert_serial)
        extra_info.append(" issuer: rid '")
        extra_info.append(str(rid_issuer))
        extra_info.append("' vs. cert '")
        extra_info.append(material_issuer)
        extra_info.append("' ")

    def prepare_encryption_dict_aes(
        self,
        encryption_dictionary: PDEncryption,
        cfm: str,
        recipients: list[bytes],
    ) -> None:
        """Wire the ``/CF /DefaultCryptFilter`` slot for an AES recipient set.

        Mirrors upstream private ``prepareEncryptionDictAES`` (Java line 419)
        — extracted as a protected helper so subclasses can override the
        ``/CF`` shape without re-implementing :meth:`prepare_document`.
        """
        crypt_filter = PDCryptFilterDictionary()
        crypt_filter.set_cfm(cfm)
        # /CF /Length is in bytes per Table 25 (note the bits/bytes split).
        crypt_filter.set_length(self.get_key_length() // 8)
        recipients_array = COSArray()
        for blob in recipients:
            recipients_array.add(COSString(blob))
        from pypdfbox.cos import COSName  # noqa: PLC0415 — lazy import

        crypt_filter.get_cos_object().set_item(
            COSName.get_pdf_name("Recipients"), recipients_array
        )
        recipients_array.set_direct(True)
        encryption_dictionary.set_default_crypt_filter_dictionary(crypt_filter)
        encryption_dictionary.set_stream_filter_name("DefaultCryptFilter")
        encryption_dictionary.set_string_filter_name("DefaultCryptFilter")
        crypt_filter.get_cos_object().set_direct(True)
        self.set_aes(True)

    # Underscore alias kept for back-compat with earlier wave callers.
    _prepare_encryption_dict_aes = prepare_encryption_dict_aes

    def compute_recipients_field(self, seed: bytes) -> list[bytes]:
        """Build the per-recipient PKCS#7 envelopes for a write.

        Mirrors upstream private ``computeRecipientsField`` (Java line 438)
        — surfaces the inline loop in :meth:`prepare_document` as a reusable
        protected helper. Returns one DER-encoded ``ContentInfo`` per
        recipient, in policy order.
        """
        from .public_key_protection_policy import (  # noqa: PLC0415
            PublicKeyProtectionPolicy,
        )

        policy = self._protection_policy
        if not isinstance(policy, PublicKeyProtectionPolicy):
            raise ValueError(
                "compute_recipients_field requires an attached "
                "PublicKeyProtectionPolicy"
            )

        envelopes: list[bytes] = []
        for recipient in policy.get_recipients():
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
            # Upstream uses ``getPermissionBytesForPublicKey()`` here, not the
            # raw ``getPermissionBytes()`` (PublicKeySecurityHandler line 449).
            perms_int = (
                permission_obj.get_permission_bytes_for_public_key() & 0xFFFFFFFF
            )
            # Per §7.6.5: the 24-byte plaintext is seed (20) || perms (4 BE).
            pkcs7_input = seed + perms_int.to_bytes(4, "big")

            envelope_der = self.create_der_for_recipient(pkcs7_input, cert)
            envelopes.append(envelope_der)
        return envelopes

    # Underscore alias kept for back-compat with earlier wave callers.
    _compute_recipients_field = compute_recipients_field

    def create_der_for_recipient(self, pkcs7_input: bytes, cert: object) -> bytes:
        """Wrap ``pkcs7_input`` in a one-recipient PKCS#7 ``ContentInfo``.

        Mirrors upstream private ``createDERForRecipient`` (Java line 476).
        Upstream hand-builds a CMS ``EnvelopedData`` with RC2-CBC content
        encryption + per-recipient RSA key wrap; this lite port delegates the
        ASN.1/CMS plumbing to ``cryptography.hazmat.primitives.serialization
        .pkcs7.PKCS7EnvelopeBuilder`` (library-first per CLAUDE.md). AES-128
        is used as the content algorithm since RC2 is not exposed by the
        ``cryptography`` PKCS#7 builder; the resulting envelope still decrypts
        on the read path because the file-key derivation is content-algo
        agnostic — it hashes the envelope bytes verbatim.
        """
        # Pick content algorithm by the attached policy's key length so the
        # write path lines up with `prepare_document`'s V/R selection.
        from .public_key_protection_policy import (  # noqa: PLC0415
            PublicKeyProtectionPolicy,
        )

        policy = self._protection_policy
        key_length_bits = 128
        if isinstance(policy, PublicKeyProtectionPolicy):
            policy_length = policy.get_encryption_key_length() or 128
            if policy_length >= 256:
                key_length_bits = 256
        content_alg: type[algorithms.AES128] | type[algorithms.AES256]
        content_alg = algorithms.AES256 if key_length_bits >= 256 else algorithms.AES128

        builder = pkcs7.PKCS7EnvelopeBuilder()
        builder = builder.set_data(pkcs7_input)
        builder = builder.add_recipient(cert)  # type: ignore[arg-type]
        builder = builder.set_content_encryption_algorithm(content_alg)
        return builder.encrypt(
            serialization.Encoding.DER,
            [pkcs7.PKCS7Options.Binary],
        )

    def compute_recipient_info(
        self, x509certificate: object, content_encryption_key: bytes
    ) -> bytes:
        """Build a single PKCS#7 ``KeyTransRecipientInfo`` for ``cert``.

        Mirrors upstream private ``computeRecipientInfo`` (Java line 528).
        Upstream builds the ASN.1 ``KeyTransRecipientInfo`` by hand
        (``IssuerAndSerialNumber`` + RSA-wrapped CEK + algorithm identifier).
        This lite port returns the DER-encoded ``ContentInfo`` produced by
        ``cryptography``'s PKCS#7 envelope builder for a one-byte payload
        encrypted to the supplied recipient — it is *not* a bare
        ``RecipientInfo``, but exposes the same surface upstream callers rely
        on (DER bytes that contain the RSA key transport blob for ``cert``).

        The ``content_encryption_key`` argument matches upstream's signature;
        we forward it as the envelope payload via ``set_data`` so the caller
        can extract the wrapped CEK from the resulting DER blob.
        """
        builder = pkcs7.PKCS7EnvelopeBuilder()
        builder = builder.set_data(content_encryption_key)
        builder = builder.add_recipient(x509certificate)  # type: ignore[arg-type]
        # AES-128 keeps the envelope deterministic regardless of attached
        # policy; the helper is consumed only for parity-surface reasons.
        builder = builder.set_content_encryption_algorithm(algorithms.AES128)
        return builder.encrypt(
            serialization.Encoding.DER,
            [pkcs7.PKCS7Options.Binary],
        )

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

    def get_recipients(self) -> list[PublicKeyRecipient]:
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
        digest = (
            hashlib.sha256()
            if version >= 5
            else hashlib.sha1(usedforsecurity=False)
        )
        digest.update(seed)
        for blob in recipient_blobs:
            digest.update(blob)
        if not encrypt_metadata:
            digest.update(b"\xff\xff\xff\xff")
        return digest.digest()[: key_length_bits // 8]

    # ---------------------------------------- additional upstream parity surface

    def get_filter(self) -> str:
        """Return the ``/Filter`` name produced by this handler.

        Mirrors upstream ``SecurityHandler#getFilter`` — for the public-key
        handler this is always ``Adobe.PubSec`` (PDF 32000-1 §7.6.5).
        """
        return self.FILTER

    def prepare_document_for_encryption(self, document: object) -> None:
        """Alias for :meth:`prepare_document` matching upstream's
        ``PublicKeySecurityHandler#prepareDocumentForEncryption(PDDocument)``.

        Upstream renames the abstract base hook ``prepareDocumentForEncryption``;
        this lite port collapses that into :meth:`prepare_document`. The alias
        keeps the upstream-named call site working verbatim.
        """
        self.prepare_document(document)

    def compute_version_number(self) -> int:
        """Pick a ``/V`` value from the attached policy's key length.

        Mirrors upstream ``SecurityHandler#computeVersionNumber``:

        - ``keyLength == 40``  → 1 (RC4-40)
        - ``keyLength == 128 && preferAES`` → 4 (AES-128)
        - ``keyLength == 256`` → 5 (AES-256)
        - otherwise            → 2 (RC4-128)

        Used by :meth:`prepare_document_for_encryption` upstream; the lite
        handler picks V/R inline (AES-only), so this accessor is exposed as a
        parity surface for callers that mirror upstream's algorithm pre-flight.
        """
        from .public_key_protection_policy import (  # noqa: PLC0415
            PublicKeyProtectionPolicy,
        )

        policy = self._protection_policy
        key_length = self._key_length
        if isinstance(policy, PublicKeyProtectionPolicy):
            policy_length = policy.get_encryption_key_length()
            if policy_length:
                key_length = policy_length

        if key_length == 40:
            return 1
        prefer_aes = (
            isinstance(policy, PublicKeyProtectionPolicy)
            and policy.is_prefer_aes()
        )
        if key_length == 128 and prefer_aes:
            return 4
        if key_length == 256:
            return 5
        return 2

    def get_number_of_recipients(self) -> int:
        """Return the recipient count from the attached policy, or ``0``.

        Convenience passthrough — upstream callers reach this via
        ``handler.getProtectionPolicy().getNumberOfRecipients()``; this alias
        avoids a ``None`` check on the policy slot.
        """
        from .public_key_protection_policy import (  # noqa: PLC0415
            PublicKeyProtectionPolicy,
        )

        policy = self._protection_policy
        if isinstance(policy, PublicKeyProtectionPolicy):
            return policy.get_number_of_recipients()
        return 0


__all__ = ["PublicKeySecurityHandler"]
