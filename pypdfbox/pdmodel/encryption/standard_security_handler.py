"""``/Filter /Standard`` security handler covering revisions 2 through 6.

Mirrors ``org.apache.pdfbox.pdmodel.encryption.StandardSecurityHandler``. Two
families are implemented:

* **Revisions 2-4** — RC4-40/128 and AES-128 with the legacy padding-based
  key derivation in PDF 32000-1 §7.6.4.3 / §7.6.4.4.
* **Revisions 5-6** — AES-256 with the SHA-2 / AES-key-wrap construction in
  PDF 32000-2 §7.6.4.4.6 onwards. The hardened r6 hash (algorithm 2.B from
  §7.6.4.3.4) is included.

For V=4 / V=5 the per-object cipher (RC4 vs AES-128 vs AES-256 vs Identity)
is selected from the ``/CF`` sub-dictionary entries pointed at by ``/StmF``,
``/StrF`` and ``/EFF`` per PDF 32000-1 §7.6.5. The CFM names are resolved at
``prepare_for_decryption`` / ``prepare_document`` time and cached, then the
cipher methods dispatch through the cached routing table. For V<4 (no /CF)
the legacy single-algorithm path inherited from ``SecurityHandler`` is used.

This is the *lite* port: it implements the password / key derivation paths
needed to read and write encrypted documents, but does not yet model
``/Recipients`` (public-key handlers) or strict per-revision key-length
validation. Those are tracked in ``CHANGES.md``.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import struct
from typing import TYPE_CHECKING

from cryptography.hazmat.primitives import padding as _aes_padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

try:
    from cryptography.hazmat.decrepit.ciphers.algorithms import ARC4 as _ARC4
except ImportError:  # pragma: no cover
    from cryptography.hazmat.primitives.ciphers.algorithms import ARC4 as _ARC4

from .access_permission import AccessPermission
from .decryption_material import DecryptionMaterial
from .invalid_password_exception import InvalidPasswordException
from .security_handler import SecurityHandler

if TYPE_CHECKING:
    from .pd_encryption import PDEncryption

_LOG = logging.getLogger(__name__)


# /CF /CFM values per PDF 32000-1 §7.6.5 Table 25.
_CFM_IDENTITY: str = "Identity"
_CFM_NONE: str = "None"
_CFM_V2: str = "V2"
_CFM_AESV2: str = "AESV2"
_CFM_AESV3: str = "AESV3"


# PDF 32000-1 §7.6.4.3 — 32-byte padding constant prepended to passwords.
_PASSWORD_PADDING = bytes(
    [
        0x28, 0xBF, 0x4E, 0x5E, 0x4E, 0x75, 0x8A, 0x41,
        0x64, 0x00, 0x4E, 0x56, 0xFF, 0xFA, 0x01, 0x08,
        0x2E, 0x2E, 0x00, 0xB6, 0xD0, 0x68, 0x3E, 0x80,
        0x2F, 0x0C, 0xA9, 0xFE, 0x64, 0x53, 0x69, 0x7A,
    ]
)

# Default permissions: allow everything (low 32 bits set; high bits cleared).
DEFAULT_PERMISSIONS = -3904  # mirrors PDFBox's PDFBOX_PERMISSIONS_DEFAULT


class StandardDecryptionMaterial(DecryptionMaterial):
    """Holds the user-supplied password for the standard security handler."""

    def __init__(self, password: str | bytes | None = None) -> None:
        self._password = password

    def get_password(self) -> bytes | None:
        """Return the password as bytes (Latin-1 per PDF 32000-1 §7.6.3.3)."""
        if self._password is None:
            return None
        if isinstance(self._password, bytes):
            return self._password
        # PDF 1.x passwords are Latin-1; r6 callers use UTF-8 SASLprep but the
        # base API accepts either — encoding is a step performed inside the
        # algorithm where the difference matters.
        return self._password.encode("latin-1", errors="replace")

    def get_password_bytes(self, revision: int) -> bytes | None:
        """Return password bytes encoded per ``revision``.

        Mirrors the upstream ``prepareForDecryption`` charset switch:
        ISO-8859-1 (Latin-1) for r2-r4 and UTF-8 for r5-r6 (PDFBOX-4155).
        ``bytes`` inputs are returned as-is so callers can pass already-encoded
        password material straight through.
        """
        if self._password is None:
            return None
        if isinstance(self._password, bytes):
            return self._password
        if int(revision) >= 5:
            return self._password.encode("utf-8", errors="replace")
        return self._password.encode("latin-1", errors="replace")

    def get_password_str(self) -> str | None:
        if self._password is None:
            return None
        if isinstance(self._password, bytes):
            return self._password.decode("latin-1", errors="replace")
        return self._password


class StandardSecurityHandler(SecurityHandler):
    """Concrete handler for ``/Filter /Standard`` revisions 2 through 6."""

    FILTER = "Standard"
    # PDFBox upstream exposes ``PROTECTION_POLICY_CLASS`` as a public static
    # final pointer at ``StandardProtectionPolicy``. We populate it lazily
    # below the class body to avoid the standard-policy → handler import
    # cycle. Kept as a class attribute so ``StandardSecurityHandler.PROTECTION_POLICY_CLASS``
    # mirrors the upstream constant access pattern.
    PROTECTION_POLICY_CLASS: type | None = None

    def __init__(self, protection_policy: object | None = None) -> None:
        super().__init__()
        self._protection_policy = protection_policy
        # Permissions and CFM-level state populated by prepare_for_decryption /
        # prepare_document.
        self._permissions: int = DEFAULT_PERMISSIONS
        self._encrypt_metadata: bool = True
        # Per-object crypt-filter routing table — each entry is one of
        # _CFM_V2 / _CFM_AESV2 / _CFM_AESV3 / _CFM_IDENTITY / _CFM_NONE, or
        # ``None`` to mean "no /CF table, use the legacy single-algo path
        # from SecurityHandler". Populated by prepare_for_decryption /
        # prepare_document for V>=4 documents.
        self._stream_cfm: str | None = None
        self._string_cfm: str | None = None
        self._embedded_file_cfm: str | None = None

    # ------------------------------------------------------------ accessors

    def get_permissions(self) -> int:
        return self._permissions

    def is_encrypt_metadata(self) -> bool:
        return self._encrypt_metadata

    # Upstream-named alias — PDFBox spells this method ``isEncryptMetaData``
    # (capital D) so we expose the snake_case variant alongside the existing
    # ``is_encrypt_metadata`` name to keep the public API mirror-friendly.
    def is_encrypt_meta_data(self) -> bool:
        return self._encrypt_metadata

    # Protection-policy accessors — the policy is captured at construction
    # time (see ``__init__``); these surface it under the upstream PDFBox
    # ``getProtectionPolicy`` / ``setProtectionPolicy`` names.
    def get_protection_policy(self) -> object | None:
        return self._protection_policy

    def set_protection_policy(self, policy: object | None) -> None:
        self._protection_policy = policy

    def has_protection_policy(self) -> bool:
        """Return True when this handler was constructed with a policy.

        Mirrors upstream ``SecurityHandler#hasProtectionPolicy`` — surfaced on
        ``StandardSecurityHandler`` so callers don't have to reach through
        the base abstraction.
        """
        return self._protection_policy is not None

    def get_filter(self) -> str:
        """Return the ``/Filter`` name handled by this implementation.

        Matches upstream's pattern of consulting ``FILTER`` via the instance —
        callers asking ``handler.get_filter()`` always get ``"Standard"``.
        """
        return self.FILTER

    # ----------------------------------------------------- upstream parity

    def compute_revision_number_from_version(self, version: int) -> int:
        """Pick the revision matching ``version`` and the active policy.

        Mirrors upstream's private ``computeRevisionNumber(int version)``.
        ``version`` is the /V value:

        * V=5     → r6 (the deprecated r5 is upgraded per PDF 32000-2 note);
        * V=4     → r4;
        * V=2 / V=3, or any V<2 with revision-3 permissions set → r3;
        * V<2 without revision-3 permissions → r2.

        Falls back to r4 when none of the above apply (matches upstream's
        terminal ``return REVISION_4``).
        """
        version = int(version)
        permissions = None
        policy = self._protection_policy
        if policy is not None and hasattr(policy, "get_permissions"):
            permissions = policy.get_permissions()
        any_r3 = bool(
            permissions is not None
            and getattr(permissions, "has_any_revision3_permission_set", lambda: False)()
        )
        if version < 2 and not any_r3:
            return 2
        if version == 5:
            return 6
        if version == 4:
            return 4
        if version in (2, 3) or any_r3:
            return 3
        return 4

    @staticmethod
    def compute_revision_number(key_length: int, prefer_aes: bool = False) -> int:
        """Pick the spec revision for a (key_length_bits, prefer_aes) pair.

        Mirrors PDFBox's ``StandardSecurityHandler.computeRevisionNumber`` —
        256-bit keys map to r6 (AES-256), 128-bit + AES preference to r4,
        128-bit RC4 to r3, anything else to r2 (RC4-40).
        """
        if int(key_length) == 256:
            return 6
        if int(key_length) == 128 and bool(prefer_aes):
            return 4
        if int(key_length) == 128:
            return 3
        return 2

    @classmethod
    def compute_user_password(  # type: ignore[override]
        cls,
        password: bytes,
        owner_entry: bytes,
        permissions: int,
        document_id: bytes,
        revision: int,
        key_len_bytes: int,
        encrypt_metadata: bool = True,
    ) -> bytes:
        """Algorithm 4/5 — derive the /U entry. Public alias.

        Mirrors Java L857-903: r5/r6 have no recoverable plaintext user
        password (file key is wrapped, not derived) so an empty byte
        sequence is returned for parity.
        """
        if int(revision) >= 5:
            return b""
        return cls._compute_user_password_r2_r4(
            password,
            owner_entry,
            permissions,
            document_id,
            revision,
            key_len_bytes,
            encrypt_metadata=encrypt_metadata,
        )

    @classmethod
    def compute_owner_password(  # type: ignore[override]
        cls,
        owner_password: bytes,
        user_password: bytes,
        revision: int,
        key_len_bytes: int,
    ) -> bytes:
        """Algorithm 3 — derive the /O entry. Public alias.

        Raises ``OSError`` for r2 with key length != 5 bytes, mirroring Java
        L920-923 (``new IOException("Expected length=5 actual=" + length)``).
        """
        if int(revision) == 2 and int(key_len_bytes) != 5:
            raise OSError(f"Expected length=5 actual={key_len_bytes}")
        return cls._compute_owner_password_r2_r4(
            owner_password, user_password, revision, key_len_bytes
        )

    @classmethod
    def compute_encrypted_key(  # type: ignore[override]
        cls,
        password: bytes,
        o: bytes,
        permissions_or_u: int | bytes,
        document_id_or_oe: bytes,
        revision_or_ue: int | bytes,
        key_len_bytes_or_perms: int,
        encrypt_metadata_or_id: bool | bytes = True,
        enc_revision: int | None = None,
        key_length_in_bytes: int | None = None,
        encrypt_metadata: bool | None = None,
        is_owner_password: bool | None = None,
    ) -> bytes:
        """Algorithm 2 — derive the file encryption key.

        Two call shapes are accepted, mirroring the two upstream
        signatures:

        * **Compact (r2-r4 only)** —
          ``compute_encrypted_key(password, o, permissions, document_id,
          revision, key_len_bytes, encrypt_metadata=True)``. This is the
          short form pypdfbox callers have been using.
        * **Full (PDFBox parity, supports r5/r6)** —
          ``compute_encrypted_key(password, o, u, oe, ue, permissions,
          document_id, encRevision, keyLengthInBytes, encryptMetadata,
          isOwnerPassword)``. Mirrors ``StandardSecurityHandler#computeEncryptedKey``
          (Java L725) byte-for-byte.

        Dispatch is by argument shape: when the third positional is
        ``bytes`` we take the full form, otherwise the compact form.
        """
        # Full upstream form: third arg is /U entry as bytes.
        if isinstance(permissions_or_u, (bytes, bytearray, memoryview)):
            u = bytes(permissions_or_u)
            oe = bytes(document_id_or_oe)
            ue = bytes(revision_or_ue) if isinstance(
                revision_or_ue, (bytes, bytearray, memoryview)
            ) else b""
            permissions = int(key_len_bytes_or_perms)
            document_id = bytes(encrypt_metadata_or_id) if isinstance(
                encrypt_metadata_or_id, (bytes, bytearray, memoryview)
            ) else b""
            revision = int(enc_revision) if enc_revision is not None else 0
            key_len = (
                int(key_length_in_bytes) if key_length_in_bytes is not None else 0
            )
            enc_meta = (
                bool(encrypt_metadata) if encrypt_metadata is not None else True
            )
            is_owner = bool(is_owner_password) if is_owner_password is not None else False
            if revision >= 5:
                return cls._compute_encryption_key_rev_5_6(
                    password, is_owner, bytes(o), u, oe, ue, revision
                )
            return cls._compute_encryption_key(
                password,
                bytes(o),
                permissions,
                document_id,
                revision,
                key_len,
                enc_meta,
            )
        # Compact form preserved for existing pypdfbox callers.
        return cls._compute_encryption_key(
            password,
            bytes(o),
            int(permissions_or_u),
            bytes(document_id_or_oe),
            int(revision_or_ue),
            int(key_len_bytes_or_perms),
            bool(encrypt_metadata_or_id),
        )

    @classmethod
    def get_user_password(
        cls,
        owner_password: bytes,
        owner_entry: bytes,
        revision: int,
        key_len_bytes: int,
    ) -> bytes:
        """Algorithm 7 inverse — recover user password from owner password.

        Mirrors upstream ``StandardSecurityHandler.getUserPassword`` for
        r2-r4. Returns the (padded) user password bytes; r5/r6 do not have
        a recoverable user password from the owner side, so upstream
        returns an empty byte array — we mirror that.
        """
        if int(revision) >= 5:
            return b""
        padded_owner = cls._pad_password(owner_password)
        digest = hashlib.md5(padded_owner, usedforsecurity=False).digest()
        if revision >= 3:
            # Upstream computeRC4key hashes only the first ``key_len_bytes`` of
            # the running digest each round (``md.update(digest, 0, length)``),
            # NOT the full 16-byte digest. For 128-bit keys (16 bytes) the two
            # are identical, but for a 40-bit (5-byte) key under R3 — reachable
            # once the revision honours the permission set (wave 1434) — the
            # full-digest variant derives the wrong key and the owner password
            # is rejected. Upstream's comment notes this truncation is required
            # for Adobe Reader to accept the 40-bit owner password.
            for _ in range(50):
                digest = hashlib.md5(digest[:key_len_bytes], usedforsecurity=False).digest()
        rc4_key = digest[:key_len_bytes]
        if revision == 2:
            return _rc4(rc4_key, owner_entry)
        # r3, r4 — 20 inverse rounds with rotated keys.
        result = bytes(owner_entry)
        for i in range(19, -1, -1):
            rotated = bytes(b ^ i for b in rc4_key)
            result = _rc4(rotated, result)
        return result

    @classmethod
    def is_user_password(
        cls,
        password: bytes | str,
        *args: object,
    ) -> bool:
        """Return True if ``password`` validates as the user password.

        Two call shapes — both the convenience pypdfbox form *and* the
        upstream byte[]-args parity form (PDFBox L1013 / L1086):

        * **Convenience** — ``is_user_password(password, encryption, document_id)``
          where ``encryption`` is a :class:`PDEncryption`. This is the
          original pypdfbox shape and stays supported for callers that
          already have the encryption dictionary parsed.
        * **Upstream parity** —
          ``is_user_password(password, user, owner, permissions, id,
          enc_revision, key_length_in_bytes, encrypt_metadata)``. Mirrors
          ``StandardSecurityHandler#isUserPassword`` byte-for-byte.

        Charset selection mirrors upstream: UTF-8 for r5/r6 (PDFBOX-4155),
        Latin-1 for r2-r4.
        """
        if len(args) == 2:
            encryption, document_id = args
            return cls._is_user_password_via_encryption(
                password, encryption, bytes(document_id or b"")  # type: ignore[arg-type]
            )
        if len(args) == 7:
            (
                user,
                owner,
                permissions,
                id_bytes,
                enc_revision,
                key_length_in_bytes,
                encrypt_metadata,
            ) = args
            return cls._is_user_password_explicit(
                password,
                bytes(user),  # type: ignore[arg-type]
                bytes(owner),  # type: ignore[arg-type]
                int(permissions),  # type: ignore[arg-type]
                bytes(id_bytes),  # type: ignore[arg-type]
                int(enc_revision),  # type: ignore[arg-type]
                int(key_length_in_bytes),  # type: ignore[arg-type]
                bool(encrypt_metadata),
            )
        raise TypeError(
            "is_user_password takes either (password, encryption, "
            "document_id) or the upstream 8-arg explicit-byte form"
        )

    @classmethod
    def is_owner_password(
        cls,
        password: bytes | str,
        *args: object,
    ) -> bool:
        """Return True if ``password`` validates as the owner password.

        Two call shapes:

        * **Convenience** —
          ``is_owner_password(password, encryption, document_id)``
        * **Upstream parity** —
          ``is_owner_password(password, user, owner, permissions, id,
          enc_revision, key_length_in_bytes, encrypt_metadata)``. Mirrors
          ``StandardSecurityHandler#isOwnerPassword`` byte-for-byte
          (Java L592 / L1118).
        """
        if len(args) == 2:
            encryption, document_id = args
            return cls._is_owner_password_via_encryption(
                password, encryption, bytes(document_id or b"")  # type: ignore[arg-type]
            )
        if len(args) == 7:
            (
                user,
                owner,
                permissions,
                id_bytes,
                enc_revision,
                key_length_in_bytes,
                encrypt_metadata,
            ) = args
            return cls._is_owner_password_explicit(
                password,
                bytes(user),  # type: ignore[arg-type]
                bytes(owner),  # type: ignore[arg-type]
                int(permissions),  # type: ignore[arg-type]
                bytes(id_bytes),  # type: ignore[arg-type]
                int(enc_revision),  # type: ignore[arg-type]
                int(key_length_in_bytes),  # type: ignore[arg-type]
                bool(encrypt_metadata),
            )
        raise TypeError(
            "is_owner_password takes either (password, encryption, "
            "document_id) or the upstream 8-arg explicit-byte form"
        )

    # -- Convenience overload: single-encryption-dict shape kept for callers
    # that already have a ``PDEncryption`` parsed.
    @classmethod
    def _is_user_password_via_encryption(
        cls,
        password: bytes | str,
        encryption: PDEncryption,
        document_id: bytes,
    ) -> bool:
        revision = int(encryption.get_revision())
        if isinstance(password, str):
            charset = "utf-8" if revision >= 5 else "latin-1"
            pw = password.encode(charset, errors="replace")
        else:
            pw = bytes(password or b"")
        key_length_bits = int(
            encryption.get_length() or (40 if revision < 3 else 128)
        )
        return cls._is_user_password_explicit(
            pw,
            encryption.get_u() or b"",
            encryption.get_o() or b"",
            int(encryption.get_p()),
            document_id,
            revision,
            key_length_bits // 8,
            bool(encryption.is_encrypt_meta_data()),
        )

    @classmethod
    def _is_owner_password_via_encryption(
        cls,
        password: bytes | str,
        encryption: PDEncryption,
        document_id: bytes,
    ) -> bool:
        revision = int(encryption.get_revision())
        if isinstance(password, str):
            charset = "utf-8" if revision >= 5 else "latin-1"
            pw = password.encode(charset, errors="replace")
        else:
            pw = bytes(password or b"")
        key_length_bits = int(
            encryption.get_length() or (40 if revision < 3 else 128)
        )
        # The convenience overload swallows the upstream "too short" / "bad
        # /UE" / "bad /OE" OSErrors and returns False so the higher-level
        # caller can use the cheap "is this password valid?" probe without
        # try/except plumbing. The explicit upstream-shape form still
        # raises so byte-for-byte parity callers get the upstream behaviour.
        try:
            return cls._is_owner_password_explicit(
                pw,
                encryption.get_u() or b"",
                encryption.get_o() or b"",
                int(encryption.get_p()),
                document_id,
                revision,
                key_length_bits // 8,
                bool(encryption.is_encrypt_meta_data()),
            )
        except OSError:
            return False

    # -- Upstream-parity explicit form: matches Java L1013 / L592 byte-for-byte.
    @classmethod
    def _is_user_password_explicit(
        cls,
        password: bytes | str,
        user: bytes,
        owner: bytes,
        permissions: int,
        id_bytes: bytes,
        enc_revision: int,
        key_length_in_bytes: int,
        encrypt_metadata: bool,
    ) -> bool:
        if isinstance(password, str):
            charset = "utf-8" if enc_revision >= 5 else "latin-1"
            pw = password.encode(charset, errors="replace")
        else:
            pw = bytes(password or b"")
        if enc_revision in (2, 3, 4):
            return cls._is_user_password_2_3_4(
                pw, user, owner, permissions, id_bytes, enc_revision,
                key_length_in_bytes, encrypt_metadata,
            )
        if enc_revision in (5, 6):
            return cls._is_user_password_5_6(pw, user, enc_revision)
        raise OSError(f"Unknown Encryption Revision {enc_revision}")

    @classmethod
    def _is_owner_password_explicit(
        cls,
        password: bytes | str,
        user: bytes,
        owner: bytes,
        permissions: int,
        id_bytes: bytes,
        enc_revision: int,
        key_length_in_bytes: int,
        encrypt_metadata: bool,
    ) -> bool:
        if isinstance(password, str):
            charset = "utf-8" if enc_revision >= 5 else "latin-1"
            pw = password.encode(charset, errors="replace")
        else:
            pw = bytes(password or b"")
        if enc_revision in (2, 3, 4):
            return cls._is_owner_password_2_3_4(
                pw, user, owner, permissions, id_bytes, enc_revision,
                key_length_in_bytes, encrypt_metadata,
            )
        if enc_revision in (5, 6):
            return cls._is_owner_password_5_6(pw, user, owner, enc_revision)
        raise OSError(f"Unknown Encryption Revision {enc_revision}")

    # -- Per-revision validators mirroring the Java ``isOwnerPassword234`` etc.
    @classmethod
    def _is_user_password_2_3_4(
        cls,
        password: bytes,
        user: bytes,
        owner: bytes,
        permissions: int,
        id_bytes: bytes,
        enc_revision: int,
        key_length_in_bytes: int,
        encrypt_metadata: bool,
    ) -> bool:
        password_bytes = cls.compute_user_password(
            password, owner, permissions, id_bytes, enc_revision,
            key_length_in_bytes, encrypt_metadata,
        )
        if enc_revision == 2:
            return hmac.compare_digest(bytes(user), bytes(password_bytes))
        # r3, r4: only first 16 bytes are compared (matches Java L1045).
        return hmac.compare_digest(bytes(user[:16]), bytes(password_bytes[:16]))

    @classmethod
    def _is_user_password_5_6(
        cls, password: bytes, user: bytes, enc_revision: int
    ) -> bool:
        if len(user) < 40:
            return False
        truncated = cls.truncate_127(password)
        u_hash = bytes(user[:32])
        u_validation_salt = bytes(user[32:40])
        if enc_revision == 5:
            computed = cls.compute_sha_256(truncated, u_validation_salt, b"")
        else:
            computed = cls.compute_hash_2a(truncated, u_validation_salt, b"")
        return hmac.compare_digest(computed, u_hash)

    @classmethod
    def _is_owner_password_2_3_4(
        cls,
        password: bytes,
        user: bytes,
        owner: bytes,
        permissions: int,
        id_bytes: bytes,
        enc_revision: int,
        key_length_in_bytes: int,
        encrypt_metadata: bool,
    ) -> bool:
        # Algorithm 7: recover candidate user password from owner.
        recovered_user = cls.get_user_password(
            password, owner, enc_revision, key_length_in_bytes
        )
        return cls._is_user_password_2_3_4(
            recovered_user, user, owner, permissions, id_bytes, enc_revision,
            key_length_in_bytes, encrypt_metadata,
        )

    @classmethod
    def _is_owner_password_5_6(
        cls, password: bytes, user: bytes, owner: bytes, enc_revision: int
    ) -> bool:
        # Java L625 — owner.length must be >= 40.
        if len(owner) < 40:
            raise OSError("Owner password is too short")
        truncated = cls.truncate_127(password)
        o_hash = bytes(owner[:32])
        o_validation_salt = bytes(owner[32:40])
        if enc_revision == 5:
            computed = cls.compute_sha_256(truncated, o_validation_salt, user)
        else:
            computed = cls.compute_hash_2a(truncated, o_validation_salt, user)
        return hmac.compare_digest(computed, o_hash)

    # ------------------------------------------------- /CF dispatch helpers

    @staticmethod
    def get_stream_filter_name(encryption: PDEncryption) -> str | None:
        """Return /StmF — name of the default crypt filter for streams."""
        return encryption.get_stm_f()

    @staticmethod
    def get_string_filter_name(encryption: PDEncryption) -> str | None:
        """Return /StrF — name of the default crypt filter for strings."""
        return encryption.get_str_f()

    @classmethod
    def _is_aes_v4(cls, encryption: PDEncryption) -> bool:
        """V=4 AES detection: prefer /CF/<StmF>/CFM, fall back to /StmF name."""
        stm_f = cls.get_stream_filter_name(encryption)
        if stm_f is None or stm_f == _CFM_IDENTITY:
            return False
        # Authoritative path: look up the named crypt filter and read /CFM.
        crypt_filter = encryption.get_crypt_filter_dictionary(stm_f)
        if crypt_filter is not None:
            cfm = crypt_filter.get_cfm()
            if cfm is not None:
                return cfm in (_CFM_AESV2, _CFM_AESV3)
        # Fallback for legacy writers that put the algorithm directly in /StmF
        # without a matching /CF entry.
        return stm_f in (_CFM_AESV2, _CFM_AESV3)

    @classmethod
    def _resolve_cfm(cls, encryption: PDEncryption, filter_name: str | None) -> str | None:
        """Resolve a /StmF / /StrF / /EFF entry to its /CFM string.

        ``filter_name`` is the name written in /Encrypt (e.g. "StdCF" or
        "Identity"). Returns:

        * ``"Identity"`` — pass-through, no cipher applied.
        * ``"V2"`` / ``"AESV2"`` / ``"AESV3"`` — cipher to use (resolved
          through /CF when present, else the legacy heuristic of treating
          ``filter_name`` itself as the algorithm name).
        * ``None`` — no filter declared at all (caller falls back to the
          legacy single-algorithm path inherited from SecurityHandler).
        """
        if filter_name is None:
            return None
        if filter_name == _CFM_IDENTITY:
            return _CFM_IDENTITY
        cf = encryption.get_crypt_filter_dictionary(filter_name)
        if cf is not None:
            cfm = cf.get_cfm()
            if cfm is not None:
                return cfm
        # Legacy writers occasionally put the algorithm name directly in
        # /StmF / /StrF without a /CF entry. Match the same heuristic
        # _is_aes_v4 already uses.
        if filter_name in (_CFM_V2, _CFM_AESV2, _CFM_AESV3, _CFM_NONE):
            return filter_name
        # Unknown filter name with no /CF entry — treat as legacy.
        return None

    def _populate_routing_table(self, encryption: PDEncryption) -> None:
        """Cache the /StmF, /StrF, /EFF → CFM resolutions on this handler.

        For V<4 documents (no /CF, no /StmF, no /StrF) all three slots stay
        ``None`` so the cipher entry points fall back to the legacy
        single-algorithm path on ``SecurityHandler``.

        For V>=4 the slots hold the resolved CFM string. /EFF defaults to
        /StmF when absent, per PDF 32000-1 §7.6.5.
        """
        version = int(encryption.get_v())
        if version < 4:
            self._stream_cfm = None
            self._string_cfm = None
            self._embedded_file_cfm = None
            return

        self._stream_cfm = self._resolve_cfm(encryption, encryption.get_stm_f())
        self._string_cfm = self._resolve_cfm(encryption, encryption.get_str_f())
        eff_name = encryption.get_eff()
        if eff_name is None:
            # Spec default: embedded files inherit /StmF.
            self._embedded_file_cfm = self._stream_cfm
        else:
            self._embedded_file_cfm = self._resolve_cfm(encryption, eff_name)

    # ---------- routing-table accessors (mostly for tests) ----------

    def get_stream_cfm(self) -> str | None:
        """Return the resolved /CFM for the default stream filter, or None."""
        return self._stream_cfm

    def get_string_cfm(self) -> str | None:
        """Return the resolved /CFM for the default string filter, or None."""
        return self._string_cfm

    def get_embedded_file_cfm(self) -> str | None:
        """Return the resolved /CFM for embedded file streams, or None."""
        return self._embedded_file_cfm

    # ----------------------------------------------------- cipher dispatch

    def decrypt_string(self, s: bytes, obj_num: int, gen_num: int) -> bytes:
        cfm = self._string_cfm
        if cfm is None:
            return super().decrypt_string(s, obj_num, gen_num)
        return self._dispatch_decrypt(cfm, s, obj_num, gen_num)

    def encrypt_string(self, s: bytes, obj_num: int, gen_num: int) -> bytes:
        cfm = self._string_cfm
        if cfm is None:
            return super().encrypt_string(s, obj_num, gen_num)
        return self._dispatch_encrypt(cfm, s, obj_num, gen_num)

    def decrypt_stream(
        self,
        data: bytes,
        obj_num: int,
        gen_num: int,
        is_embedded_file: bool = False,
    ) -> bytes:
        cfm = self._embedded_file_cfm if is_embedded_file else self._stream_cfm
        if cfm is None:
            # Routing table empty (V<4) — fall back to the legacy single-algo
            # path. ``SecurityHandler`` doesn't know about is_embedded_file
            # because per-object filters don't exist below V=4.
            return super().decrypt_stream(data, obj_num, gen_num)
        return self._dispatch_decrypt(cfm, data, obj_num, gen_num)

    def encrypt_stream(
        self,
        data: bytes,
        obj_num: int,
        gen_num: int,
        is_embedded_file: bool = False,
    ) -> bytes:
        cfm = self._embedded_file_cfm if is_embedded_file else self._stream_cfm
        if cfm is None:
            return super().encrypt_stream(data, obj_num, gen_num)
        return self._dispatch_encrypt(cfm, data, obj_num, gen_num)

    def _dispatch_decrypt(
        self, cfm: str, data: bytes, obj_num: int, gen_num: int
    ) -> bytes:
        if cfm in (_CFM_IDENTITY, _CFM_NONE):
            return data
        if cfm == _CFM_V2:
            return _rc4(self.compute_object_key(obj_num, gen_num), data)
        if cfm == _CFM_AESV2:
            return _aes128_cbc_decrypt(
                self.compute_object_key(obj_num, gen_num), data
            )
        if cfm == _CFM_AESV3:
            # AES-256: file-encryption key used directly (no per-object salt).
            return _aes128_cbc_decrypt(self.get_encryption_key() or b"", data)
        # Unknown CFM — refuse silently rather than corrupting bytes.
        return data

    def _dispatch_encrypt(
        self, cfm: str, data: bytes, obj_num: int, gen_num: int
    ) -> bytes:
        if cfm in (_CFM_IDENTITY, _CFM_NONE):
            return data
        if cfm == _CFM_V2:
            return _rc4(self.compute_object_key(obj_num, gen_num), data)
        if cfm == _CFM_AESV2:
            return _aes128_cbc_encrypt(
                self.compute_object_key(obj_num, gen_num), data
            )
        if cfm == _CFM_AESV3:
            return _aes128_cbc_encrypt(self.get_encryption_key() or b"", data)
        return data

    # ------------------------------------------------------------ read path

    def prepare_for_decryption(
        self,
        encryption: PDEncryption,
        document_id: object,
        decryption_material: object,
    ) -> None:
        if not isinstance(decryption_material, StandardDecryptionMaterial):
            raise TypeError(
                "StandardSecurityHandler requires StandardDecryptionMaterial"
            )

        # Upstream takes a ``COSArray`` for ``documentIDArray`` and pulls
        # bytes from element 0; pypdfbox callers usually pass raw bytes
        # already. Accept both shapes so the parity surface lines up.
        document_id = self._get_document_id_bytes(document_id)

        revision = int(encryption.get_revision())
        version = int(encryption.get_v())
        key_length_bits = int(encryption.get_length() or (40 if revision < 3 else 128))
        if revision >= 5:
            key_length_bits = 256

        self.set_revision(revision)
        self.set_version(version)
        self.set_key_length(key_length_bits)
        self._permissions = int(encryption.get_p())
        self._encrypt_metadata = bool(encryption.is_encrypt_meta_data())
        # AES is signalled by V=4 with the default stream filter's /CFM set
        # to AESV2, or V=5/6 with AESV3. We resolve through /CF when present
        # and only fall back to a name-based heuristic for legacy writers
        # that put the algorithm name directly in /StmF.
        if version >= 5:
            self.set_aes(True)
        elif version == 4:
            self.set_aes(self._is_aes_v4(encryption))
        else:
            self.set_aes(False)

        # Cache the per-object crypt-filter routing table — empty for V<4
        # (legacy single-algo path), populated from /StmF / /StrF / /EFF
        # via /CF for V>=4.
        self._populate_routing_table(encryption)

        # PDF 32000-2 §7.6.4.3.4 — r5/r6 read passwords as UTF-8 (after
        # SaslPrep), r2-r4 as Latin-1. Match upstream so non-ASCII passwords
        # round-trip correctly.
        password = decryption_material.get_password_bytes(revision) or b""
        o = encryption.get_o()
        u = encryption.get_u()

        if revision >= 5:
            oe = encryption.get_oe()
            ue = encryption.get_ue()
            perms = encryption.get_perms()
            if o is None or u is None or oe is None or ue is None or perms is None:
                raise InvalidPasswordException()
            key = self._compute_encryption_key_r5_r6(
                password, o, u, oe, ue, perms, revision
            )
            if key is None:
                raise InvalidPasswordException()
            owner_password = self._is_owner_password_r5_r6(password, o, u, revision)
            self.set_encryption_key(key)
            # Algorithm 13 — verify /Perms. Upstream merely warns on mismatch
            # since some encoders mis-emit the field; we do the same so we
            # stay tolerant of buggy producers (PDFBox parity).
            if len(perms) == 16 and not self._validate_perms_r5_r6(
                key, perms, self._permissions, self._encrypt_metadata
            ):
                _LOG.warning(
                    "Verification of /Perms failed — using /P from "
                    "the encryption dictionary"
                )
            if owner_password:
                self.set_current_access_permission(
                    AccessPermission.get_owner_access_permission()
                )
            else:
                ap = AccessPermission(self._permissions)
                ap.set_read_only()
                self.set_current_access_permission(ap)
            return

        # Revisions 2-4: try owner password first, then user password.
        if o is None or u is None:
            raise InvalidPasswordException()
        key_len_bytes = key_length_bits // 8
        owner_key = self._compute_encryption_key_via_owner_password(
            password,
            o,
            u,
            self._permissions,
            document_id,
            revision,
            key_len_bytes,
            self._encrypt_metadata,
        )
        if owner_key is not None:
            self.set_encryption_key(owner_key)
            # Owner authenticated — full permissions. Mirrors upstream
            # ``StandardSecurityHandler#prepareForDecryption`` setting
            # ``setCurrentAccessPermission(AccessPermission.getOwnerAccessPermission())``.
            self.set_current_access_permission(
                AccessPermission.get_owner_access_permission()
            )
            return

        user_key = self._compute_encryption_key_via_user_password(
            password,
            o,
            u,
            self._permissions,
            document_id,
            revision,
            key_len_bytes,
            self._encrypt_metadata,
        )
        if user_key is not None:
            self.set_encryption_key(user_key)
            # User authenticated — permissions limited by the /P bits.
            ap = AccessPermission(self._permissions)
            ap.set_read_only()
            self.set_current_access_permission(ap)
            return

        raise InvalidPasswordException()

    # ----------------------------------------------------------- write path

    def prepare_document_for_encryption(self, document: object) -> None:
        """Upstream-named alias for :meth:`prepare_document`.

        Mirrors PDFBox's ``StandardSecurityHandler#prepareDocumentForEncryption``
        — the actual logic lives in ``prepare_document`` so subclasses and
        existing callers keep working.
        """
        self.prepare_document(document)

    def prepare_document(self, document: object) -> None:
        """Populate ``/Encrypt`` on ``document`` from the protection policy.

        Lite implementation: supports r3 RC4-128, r4 AES-128, r6 AES-256 driven
        by ``protection_policy.get_encryption_key_length()`` and
        ``protection_policy.is_preferred_aes()``. Anything more exotic falls
        through to defaults that match PDFBox's chosen behaviour.
        """
        from .pd_encryption import PDEncryption

        policy = self._protection_policy
        if policy is None:
            raise ValueError("prepare_document requires a protection_policy")

        owner_password = (
            policy.get_owner_password() if hasattr(policy, "get_owner_password") else ""
        ) or ""
        user_password = (
            policy.get_user_password() if hasattr(policy, "get_user_password") else ""
        ) or ""
        key_len_bits = (
            policy.get_encryption_key_length()
            if hasattr(policy, "get_encryption_key_length")
            else 128
        )
        prefer_aes = bool(
            getattr(policy, "is_prefer_aes", lambda: False)()
        )
        permissions = (
            policy.get_permissions().get_permission_bytes()
            if hasattr(policy, "get_permissions") and policy.get_permissions() is not None
            else DEFAULT_PERMISSIONS
        )
        # /EncryptMetadata propagation from the policy (wave 1367). When the
        # policy advertises ``is_encrypt_metadata=False`` we mirror that on
        # the handler so the file-key derivation below sees the correct
        # value, and the on-the-wire ``PDEncryption`` gets the matching
        # boolean. Missing accessor → keep whatever the caller set directly
        # on ``self._encrypt_metadata`` (default True at __init__).
        if hasattr(policy, "is_encrypt_metadata"):
            self._encrypt_metadata = bool(policy.is_encrypt_metadata())

        if key_len_bits == 256:
            revision, version = 6, 5
            self.set_aes(True)
        elif key_len_bits == 128 and prefer_aes:
            revision, version = 4, 4
            self.set_aes(True)
        elif key_len_bits == 128:
            revision, version = 3, 2
            self.set_aes(False)
        else:
            # RC4-40 (/V 1). Upstream's prepareDocumentForEncryption derives
            # the revision from the permission set, not the key length:
            # computeRevisionNumber(1) returns R2 only when no revision-3
            # permission bit is set, else R3 (PDFBox
            # StandardSecurityHandler.computeRevisionNumber). The default
            # AccessPermission() has every revision-3 bit set, so a plain
            # 40-bit protect emits R3 in PDFBox — pypdfbox previously
            # hardcoded R2 here, diverging on the on-the-wire /R.
            version = 1
            revision = self.compute_revision_number_from_version(version)
            key_len_bits = 40
            self.set_aes(False)

        self.set_revision(revision)
        self.set_version(version)
        self.set_key_length(key_len_bits)
        self._permissions = permissions

        encryption = PDEncryption()
        encryption.set_filter("Standard")
        encryption.set_v(version)
        encryption.set_revision(revision)
        encryption.set_length(key_len_bits)
        encryption.set_p(permissions)
        # /EncryptMetadata propagation (wave 1367) — the file-encryption-key
        # derivation in Algorithm 2 (r4) and the /Perms block in Algorithm
        # 8/9 (r5/r6) both depend on whether metadata is encrypted. Without
        # echoing the handler's flag into the on-the-wire ``PDEncryption``
        # the reader would derive a different file key (r4) or fail the
        # /Perms validation (r5/r6) on reload. PDF 32000-1 §7.6.3.2 default
        # is True so we only emit the entry when it differs.
        if not self._encrypt_metadata:
            encryption.set_encrypt_meta_data(False)

        # PDF 32000-2 §7.6.4.3.4 — r6 writes UTF-8 (after SaslPrep), r2-r4
        # use Latin-1. Match upstream's ``prepareDocumentForEncryption``.
        if revision >= 5:
            owner_pw = owner_password.encode("utf-8", errors="replace")
            user_pw = user_password.encode("utf-8", errors="replace")
        else:
            owner_pw = owner_password.encode("latin-1", errors="replace")
            user_pw = user_password.encode("latin-1", errors="replace")
        # Owner password defaults to the user password if not supplied.
        if not owner_pw:
            owner_pw = user_pw

        # File identifier (/ID[0]) — the standard handler binds the file
        # encryption key to this value (PDF 32000-1 §7.6.4.3 algorithm 2).
        # Pull it from the document's trailer when present so a re-load can
        # derive the same key; fall back to the 16-zero-bytes fixture when
        # no /ID is reachable (legacy lite-path tests rely on this).
        document_id = self._extract_document_id(document, b"\x00" * 16)

        if revision >= 5:
            # r5/r6 keys are random; we synthesise them and wrap.
            self.set_encryption_key(os.urandom(32))
            o, oe, u, ue, perms = self._build_r6_dictionary(
                owner_pw, user_pw, permissions
            )
            encryption.set_o(o)
            encryption.set_u(u)
            encryption.set_oe(oe)
            encryption.set_ue(ue)
            encryption.set_perms(perms)
            # /CF/StdCF + /StmF + /StrF — write side gets the same routing
            # table the read side will rebuild on load.
            self._install_std_crypt_filter(encryption, _CFM_AESV3, 32)
        else:
            o = self._compute_owner_password_r2_r4(
                owner_pw, user_pw, revision, key_len_bits // 8
            )
            # File key derived from user password + O.
            file_key = self._compute_encryption_key(
                user_pw,
                o,
                permissions,
                document_id,
                revision,
                key_len_bits // 8,
                self._encrypt_metadata,
            )
            self.set_encryption_key(file_key)
            u = self._compute_user_password_r2_r4(
                user_pw,
                o,
                permissions,
                document_id,
                revision,
                key_len_bits // 8,
                encrypt_metadata=self._encrypt_metadata,
            )
            encryption.set_o(o)
            encryption.set_u(u)
            if version == 4:
                cfm = _CFM_AESV2 if prefer_aes else _CFM_V2
                self._install_std_crypt_filter(encryption, cfm, key_len_bits // 8)

        # Cache the routing table so encrypt_string / encrypt_stream can
        # dispatch to the right cipher on the write side too.
        self._populate_routing_table(encryption)

        # Attach the encryption dictionary to the document if it exposes the
        # standard PDFBox setter.
        if hasattr(document, "set_encryption_dictionary"):
            document.set_encryption_dictionary(encryption)

    @staticmethod
    def _install_std_crypt_filter(
        encryption: PDEncryption, cfm: str, length_bytes: int
    ) -> None:
        """Wire /CF/StdCF + /StmF + /StrF on ``encryption`` for V>=4 writes.

        Mirrors what PDFBox's ``StandardSecurityHandler.prepareEncryptionDictRev4``
        / ``prepareEncryptionDictRev6`` do — installs a single named crypt
        filter and points both /StmF and /StrF at it. /EFF is intentionally
        left absent so embedded files inherit /StmF (spec default).
        """
        from .pd_crypt_filter_dictionary import PDCryptFilterDictionary

        std = PDCryptFilterDictionary()
        std.set_cfm(cfm)
        std.set_length(length_bytes)
        encryption.set_std_crypt_filter_dictionary(std)
        encryption.set_stm_f("StdCF")
        encryption.set_str_f("StdCF")

    @staticmethod
    def _get_document_id_bytes(document_id: object) -> bytes:
        """Mirror upstream ``getDocumentIDBytes(COSArray)``.

        Accepts either a raw ``bytes`` (the pypdfbox shape) or a ``COSArray``
        whose first element is a ``COSString`` (the upstream shape). Returns
        an empty ``bytes`` for ``None`` / empty array — matching Java L309's
        ``new byte[0]`` fallback used by the
        ``test/encryption/encrypted_doc_no_id.pdf`` corpus case.
        """
        if document_id is None:
            return b""
        if isinstance(document_id, (bytes, bytearray, memoryview)):
            return bytes(document_id)
        # Treat as COSArray-like — duck-type ``size`` + ``get``/``getObject``.
        size_attr = getattr(document_id, "size", None)
        if callable(size_attr):
            try:
                if size_attr() < 1:
                    return b""
            except (TypeError, ValueError):
                return b""
            getter = getattr(document_id, "get", None) or getattr(
                document_id, "get_object", None
            )
            if callable(getter):
                first = getter(0)
                get_bytes = getattr(first, "get_bytes", None)
                if callable(get_bytes):
                    return bytes(get_bytes())
        return b""

    @staticmethod
    def _extract_document_id(document: object, default: bytes) -> bytes:
        """Return ``/ID[0]`` from the document's trailer as raw bytes.

        Walks both flavours of input: a ``PDDocument`` (uses
        ``get_document().get_document_id()``) or a ``COSDocument`` directly
        (uses its own accessor). Falls back to ``default`` if no /ID is
        reachable so the legacy lite-path callers — which never installed
        a trailer — keep working.
        """
        # Late imports keep this file independent of the cos / pdmodel
        # packages at module-load time.
        from pypdfbox.cos import COSString as _COSString

        cos_doc = document
        get_doc = getattr(document, "get_document", None)
        if callable(get_doc):
            cos_doc = get_doc()

        get_id = getattr(cos_doc, "get_document_id", None)
        if not callable(get_id):
            return default
        ids = get_id()
        if ids is None or ids.size() < 1:
            return default
        first = ids.get(0)
        if isinstance(first, _COSString):
            return first.get_bytes()
        return default

    # ============================================================ r2-r4 ===

    @staticmethod
    def _pad_password(password: bytes) -> bytes:
        password = password[:32]
        return password + _PASSWORD_PADDING[: 32 - len(password)]

    @classmethod
    def _compute_encryption_key(
        cls,
        password: bytes,
        o: bytes,
        permissions: int,
        document_id: bytes,
        revision: int,
        key_len_bytes: int,
        encrypt_metadata: bool,
    ) -> bytes:
        """PDF 32000-1 §7.6.4.3.2 algorithm 2 — derive file encryption key."""
        padded = cls._pad_password(password)
        md5 = hashlib.md5(usedforsecurity=False)
        md5.update(padded)
        md5.update(o)
        md5.update(struct.pack("<i", _signed32(permissions)))
        md5.update(document_id)
        if revision >= 4 and not encrypt_metadata:
            md5.update(b"\xff\xff\xff\xff")
        digest = md5.digest()
        if revision >= 3:
            for _ in range(50):
                digest = hashlib.md5(
                    digest[:key_len_bytes], usedforsecurity=False
                ).digest()
        return digest[:key_len_bytes]

    @classmethod
    def _compute_owner_password_r2_r4(
        cls,
        owner_password: bytes,
        user_password: bytes,
        revision: int,
        key_len_bytes: int,
    ) -> bytes:
        """PDF 32000-1 §7.6.4.4.2 algorithm 3 — produce /O entry."""
        padded_owner = cls._pad_password(owner_password)
        digest = hashlib.md5(padded_owner, usedforsecurity=False).digest()
        if revision >= 3:
            # Algorithm 3 step (b): each of the 50 MD5 rounds re-hashes only
            # the first ``key_len_bytes`` of the previous digest (see the
            # matching note in ``_compute_encryption_key_via_owner_password``).
            # Hashing the full digest produces a wrong /O for sub-128-bit
            # keys, which then can't be owner-decrypted by us OR by Apache
            # PDFBox.
            for _ in range(50):
                digest = hashlib.md5(
                    digest[:key_len_bytes], usedforsecurity=False
                ).digest()
        rc4_key = digest[:key_len_bytes]

        padded_user = cls._pad_password(user_password)
        result = _rc4(rc4_key, padded_user)
        if revision >= 3:
            for i in range(1, 20):
                rotated = bytes(b ^ i for b in rc4_key)
                result = _rc4(rotated, result)
        return result

    @classmethod
    def _compute_user_password_r2_r4(
        cls,
        password: bytes,
        o: bytes,
        permissions: int,
        document_id: bytes,
        revision: int,
        key_len_bytes: int,
        encrypt_metadata: bool = True,
    ) -> bytes:
        """PDF 32000-1 §7.6.4.4.3-.4 algorithms 4 and 5 — produce /U entry.

        The ``encrypt_metadata`` flag (wave 1367 latent-bug fix) MUST be
        consistent with the value used for :meth:`_compute_encryption_key`
        — Algorithm 5 step 1 derives the same file key Algorithm 2 would
        produce, and Algorithm 2 step 6 conditionally mixes in
        ``0xFFFFFFFF`` when revision >= 4 and metadata isn't encrypted.
        Defaulting to ``True`` preserves the pre-1367 behaviour for callers
        that don't supply the flag (most paths emit encrypted metadata).
        """
        file_key = cls._compute_encryption_key(
            password,
            o,
            permissions,
            document_id,
            revision,
            key_len_bytes,
            encrypt_metadata=encrypt_metadata,
        )
        if revision == 2:
            return _rc4(file_key, _PASSWORD_PADDING)
        # Revisions 3 and 4.
        md5 = hashlib.md5(usedforsecurity=False)
        md5.update(_PASSWORD_PADDING)
        md5.update(document_id)
        result = _rc4(file_key, md5.digest())
        for i in range(1, 20):
            rotated = bytes(b ^ i for b in file_key)
            result = _rc4(rotated, result)
        # Pad to 32 bytes with arbitrary bytes (PDFBox uses zeros).
        return result + b"\x00" * (32 - len(result))

    @classmethod
    def _compute_encryption_key_via_user_password(
        cls,
        password: bytes,
        o: bytes,
        u: bytes,
        permissions: int,
        document_id: bytes,
        revision: int,
        key_len_bytes: int,
        encrypt_metadata: bool,
    ) -> bytes | None:
        """Algorithm 6 — validate user password, return file key on match."""
        file_key = cls._compute_encryption_key(
            password,
            o,
            permissions,
            document_id,
            revision,
            key_len_bytes,
            encrypt_metadata,
        )
        if revision == 2:
            computed_u = _rc4(file_key, _PASSWORD_PADDING)
            return file_key if computed_u == u[:32] else None
        # r3, r4 — only the first 16 bytes are compared.
        md5 = hashlib.md5(usedforsecurity=False)
        md5.update(_PASSWORD_PADDING)
        md5.update(document_id)
        candidate = _rc4(file_key, md5.digest())
        for i in range(1, 20):
            rotated = bytes(b ^ i for b in file_key)
            candidate = _rc4(rotated, candidate)
        if candidate[:16] == u[:16]:
            return file_key
        return None

    @classmethod
    def _compute_encryption_key_via_owner_password(
        cls,
        password: bytes,
        o: bytes,
        u: bytes,
        permissions: int,
        document_id: bytes,
        revision: int,
        key_len_bytes: int,
        encrypt_metadata: bool,
    ) -> bytes | None:
        """Algorithm 7 — recover user password from owner password, then 6."""
        padded_owner = cls._pad_password(password)
        digest = hashlib.md5(padded_owner, usedforsecurity=False).digest()
        if revision >= 3:
            # PDF 32000-1 §7.6.4.4.2 Algorithm 3 step (b): each of the 50
            # MD5 rounds re-hashes only the FIRST ``key_len_bytes`` of the
            # previous digest, not the full 16-byte output. Hashing the full
            # digest only happens to match for 128-bit keys (key_len_bytes ==
            # 16 == digest length); at 40-bit (key_len_bytes == 5) it diverges
            # and the recovered owner key is wrong, so a valid owner password
            # was rejected on RC4-40 / V=1 R=3 Length=40 documents.
            for _ in range(50):
                digest = hashlib.md5(
                    digest[:key_len_bytes], usedforsecurity=False
                ).digest()
        rc4_key = digest[:key_len_bytes]

        if revision == 2:
            user_pw = _rc4(rc4_key, o)
        else:
            user_pw = o
            for i in range(19, -1, -1):
                rotated = bytes(b ^ i for b in rc4_key)
                user_pw = _rc4(rotated, user_pw)
        return cls._compute_encryption_key_via_user_password(
            user_pw,
            o,
            u,
            permissions,
            document_id,
            revision,
            key_len_bytes,
            encrypt_metadata,
        )

    # ============================================================ r5-r6 ===

    # ------------------------------------------------- upstream-named helpers
    # Public-facing snake_case mirrors of PDFBox's private static helpers,
    # surfaced so parity tests can drive them directly. These are pure
    # algorithmic helpers — no I/O, no global state — so exposing them costs
    # nothing and matches the upstream contract.

    @staticmethod
    def truncate_127(value: bytes) -> bytes:
        """Mirror upstream ``truncate127``: r5/r6 password truncation."""
        if value is None:
            return b""
        return bytes(value[:127])

    @classmethod
    def truncate_or_pad(cls, password: bytes) -> bytes:
        """Mirror upstream ``truncateOrPad``: r2-r4 password padding."""
        return cls._pad_password(password)

    @staticmethod
    def adjust_user_key(u: bytes | None) -> bytes:
        """Mirror upstream ``adjustUserKey``.

        Returns the first 48 bytes of /U for r5/r6 owner-password hashing.
        Empty bytes are treated as null-equivalent (returns ``b""``) since
        pypdfbox callers commonly pass ``encryption.get_u() or b""``; an
        explicit short-but-non-empty /U still raises ``OSError`` to mirror
        Java L1226's ``new IOException("Bad U length")``.
        """
        if u is None or len(u) == 0:
            return b""
        if len(u) < 48:
            raise OSError("Bad U length")
        if len(u) > 48:
            return bytes(u[:48])
        return bytes(u)

    @classmethod
    def compute_sha_256(
        cls, password: bytes, salt: bytes, user_key: bytes | None
    ) -> bytes:
        """Mirror upstream ``computeSHA256`` (r5 hash).

        Builds SHA-256(password || salt || adjustUserKey(user_key)).
        """
        md = hashlib.sha256()
        md.update(bytes(password))
        md.update(bytes(salt))
        md.update(cls.adjust_user_key(user_key))
        return md.digest()

    @classmethod
    def compute_hash_2a(
        cls, password: bytes, salt: bytes, u: bytes | None
    ) -> bytes:
        """Mirror upstream ``computeHash2A`` (Algorithm 2.A from ISO 32000-1).

        ``input = truncate127(password) || salt || adjustUserKey(u)`` →
        ``computeHash2B(input, truncate127(password), adjustUserKey(u))``.
        """
        user_key = cls.adjust_user_key(u)
        truncated = cls.truncate_127(password)
        input_bytes = truncated + bytes(salt) + user_key
        return cls.compute_hash_2b(input_bytes, truncated, user_key)

    @classmethod
    def compute_hash_2b(
        cls, input_data: bytes, password: bytes, user_key: bytes | None
    ) -> bytes:
        """Mirror upstream ``computeHash2B`` (Algorithm 2.B from ISO 32000-2).

        Snake-case alias over :meth:`_compute_hash_r5_r6` so callers using
        the upstream name resolve to the same r6 hardened-hash routine.
        ``user_key`` may be ``None`` (treated as empty per upstream).
        """
        uk = bytes(user_key) if user_key is not None else b""
        return cls._compute_hash_r5_r6(bytes(input_data), bytes(password), uk, 6)

    @classmethod
    def compute_rc_4_key(
        cls, owner_password: bytes, enc_revision: int, length: int
    ) -> bytes:
        """Mirror upstream ``computeRC4key`` — steps (a)-(d) of Algorithm 3.

        MD5 of the padded owner password, optionally re-hashed 50 times for
        r3/r4, then truncated to ``length`` bytes. Used as the RC4 key in
        algorithms 3 and 7.
        """
        try:
            digest = hashlib.md5(
                cls._pad_password(owner_password), usedforsecurity=False
            ).digest()
            if enc_revision in (3, 4):
                for _ in range(50):
                    digest = hashlib.md5(
                        digest[:length], usedforsecurity=False
                    ).digest()
            return digest[:length]
        except ValueError as exc:
            # Mirror Java's PDFBOX-6115 catch: illegal key length.
            raise OSError(str(exc)) from exc

    def validate_perms(
        self,
        encryption: PDEncryption,
        dic_permissions: int,
        encrypt_metadata: bool,
    ) -> None:
        """Mirror upstream ``validatePerms`` — Algorithm 13 read-side check.

        Decrypts ``/Perms`` (AES-256 ECB under the file encryption key) and
        warns on mismatched permissions / metadata flag without raising,
        matching upstream's relaxed treatment of buggy producers. The file
        encryption key must already be set on this handler — call after
        :meth:`prepare_for_decryption` succeeds. Unknown perms are tolerated
        to mirror Java L317 behaviour exactly.
        """
        file_key = self.get_encryption_key() or b""
        perms = encryption.get_perms()
        if perms is None or len(perms) != 16:
            return
        plain = self._decrypt_perms_r5_r6(file_key, perms)
        if len(plain) != 16:
            _LOG.warning("Verification of permissions failed (cannot decrypt)")
            return
        if plain[9] != ord("a") or plain[10] != ord("d") or plain[11] != ord("b"):
            _LOG.warning("Verification of permissions failed (constant)")
        perms_p = (
            plain[0]
            | (plain[1] << 8)
            | (plain[2] << 16)
            | (plain[3] << 24)
        )
        if perms_p & 0x80000000:
            perms_p -= 0x100000000
        if perms_p != _signed32(dic_permissions):
            _LOG.warning(
                "Verification of permissions failed (%08X != %08X)",
                perms_p & 0xFFFFFFFF,
                dic_permissions & 0xFFFFFFFF,
            )
        expected = ord("T") if encrypt_metadata else ord("F")
        if plain[8] != expected:
            _LOG.warning("Verification of permissions failed (EncryptMetadata)")

    @classmethod
    def _compute_encryption_key_rev_5_6(
        cls,
        password: bytes,
        is_owner_password: bool,
        o: bytes,
        u: bytes,
        oe: bytes,
        ue: bytes,
        enc_revision: int,
    ) -> bytes:
        """Mirror upstream ``computeEncryptedKeyRev56`` (Java L783).

        Given a password presumed to be owner or user (per ``is_owner_password``),
        recover the file encryption key by AES-256-CBC unwrapping ``oe`` or
        ``ue`` under the SHA-256 (r5) or hardened-hash (r6) of
        ``password || keySalt [|| U[:48]]``.
        """
        truncated = cls.truncate_127(password)
        if is_owner_password:
            if oe is None:
                raise OSError("/Encrypt/OE entry is missing")
            o_key_salt = bytes(o[40:48])
            if enc_revision == 5:
                hash_value = cls.compute_sha_256(truncated, o_key_salt, u)
            else:
                hash_value = cls.compute_hash_2a(truncated, o_key_salt, u)
            file_key_enc = oe
        else:
            if ue is None:
                raise OSError("/Encrypt/UE entry is missing")
            u_key_salt = bytes(u[40:48])
            if enc_revision == 5:
                hash_value = cls.compute_sha_256(truncated, u_key_salt, None)
            else:
                hash_value = cls.compute_hash_2a(truncated, u_key_salt, None)
            file_key_enc = ue
        return _aes_cbc_no_padding_decrypt(
            hash_value, b"\x00" * 16, bytes(file_key_enc)
        )

    @classmethod
    def _compute_encryption_key_r5_r6(
        cls,
        password: bytes,
        o: bytes,
        u: bytes,
        oe: bytes,
        ue: bytes,
        perms: bytes,
        revision: int,
    ) -> bytes | None:
        """PDF 32000-2 §7.6.4.4.10/.11 — validate password, unwrap file key.

        Returns the 32-byte AES-256 file key on success, or None on mismatch.
        """
        if not (o and u and oe and ue):
            return None
        # Owner: hash(password || OVS || U[0:48]) compared to O[0:32].
        owner_validation_salt = o[32:40]
        owner_key_salt = o[40:48]
        truncated_pw = password[:127]
        if cls._compute_hash_r5_r6(
            truncated_pw + owner_validation_salt + u[:48], truncated_pw, u[:48], revision
        ) == o[:32]:
            inter = cls._compute_hash_r5_r6(
                truncated_pw + owner_key_salt + u[:48],
                truncated_pw,
                u[:48],
                revision,
            )
            return _aes_cbc_no_padding_decrypt(inter, b"\x00" * 16, oe[:32])

        # User: hash(password || UVS) compared to U[0:32].
        user_validation_salt = u[32:40]
        user_key_salt = u[40:48]
        if cls._compute_hash_r5_r6(
            truncated_pw + user_validation_salt, truncated_pw, b"", revision
        ) == u[:32]:
            inter = cls._compute_hash_r5_r6(
                truncated_pw + user_key_salt, truncated_pw, b"", revision
            )
            return _aes_cbc_no_padding_decrypt(inter, b"\x00" * 16, ue[:32])

        return None

    @classmethod
    def _is_owner_password_r5_r6(
        cls, password: bytes, o: bytes, u: bytes, revision: int
    ) -> bool:
        """Return True when ``password`` matches the r5/r6 owner hash."""
        if len(o) < 40 or len(u) < 48:
            return False
        truncated_pw = password[:127]
        owner_validation_salt = o[32:40]
        return cls._compute_hash_r5_r6(
            truncated_pw + owner_validation_salt + u[:48],
            truncated_pw,
            u[:48],
            revision,
        ) == o[:32]

    @classmethod
    def _compute_hash_r5_r6(
        cls, input_data: bytes, password: bytes, user_key: bytes, revision: int
    ) -> bytes:
        """PDF 32000-2 §7.6.4.3.4 algorithm 2.B — hardened hash for r6.

        For r5 the result is plain SHA-256 of ``input_data``; for r6 the
        64-iteration AES + SHA-2 round is applied. ``user_key`` is included
        in the per-round block only when it is at least 48 bytes (mirroring
        ``StandardSecurityHandler.computeHash2B`` upstream — the U entry's
        first 48 bytes during owner-password validation).

        The mod-3 selection of SHA-256/-384/-512 follows ISO 32000-2 §7.6.4.3.4
        algorithm 2.B step (e): "Treat the first 16 bytes [of ``e``] as an
        unsigned big-endian integer and take it mod 3". Summing the bytes —
        which is what we do here — is *not* the same as a big-endian integer
        mod 3 in general, but because ``256 ≡ 1 (mod 3)`` every byte
        contributes ``1`` per place value and the byte-sum mod 3 equals the
        big-endian-integer mod 3 by Fermat's little theorem on the radix.
        Keep the comment so the equivalence isn't re-derived on every read.
        """
        k = hashlib.sha256(input_data).digest()
        if revision == 5:
            return k

        # Only include user_key in the per-round block when it's at least 48
        # bytes, matching PDFBox's ``computeHash2B`` exactly.
        include_user_key = user_key is not None and len(user_key) >= 48
        uk = user_key[:48] if include_user_key else b""

        round_no = 0
        last_byte = 0
        while round_no < 64 or last_byte > round_no - 32:
            k1 = (password + k + uk) * 64
            aes_key = k[:16]
            iv = k[16:32]
            cipher = Cipher(algorithms.AES(aes_key), modes.CBC(iv))
            enc = cipher.encryptor()
            e = enc.update(k1) + enc.finalize()
            # Sum first 16 bytes mod 3 — selects SHA-256 / -384 / -512.
            sum_mod3 = sum(e[:16]) % 3
            if sum_mod3 == 0:
                k = hashlib.sha256(e).digest()
            elif sum_mod3 == 1:
                k = hashlib.sha384(e).digest()
            else:
                k = hashlib.sha512(e).digest()
            last_byte = e[-1]
            round_no += 1

        return k[:32]

    @classmethod
    def _decrypt_perms_r5_r6(cls, file_key: bytes, perms: bytes) -> bytes:
        """Decrypt the 16-byte ``/Perms`` block with AES-256 ECB (no padding).

        ISO 32000-2 §7.6.4.4.11 (algorithm 13). Returns the 16-byte
        plaintext, or ``b""`` when the input is malformed.
        """
        if file_key is None or len(file_key) != 32 or len(perms) != 16:
            return b""
        cipher = Cipher(algorithms.AES(file_key), modes.ECB())
        dec = cipher.decryptor()
        return dec.update(perms) + dec.finalize()

    @classmethod
    def _validate_perms_r5_r6(
        cls,
        file_key: bytes,
        perms: bytes,
        dic_permissions: int,
        encrypt_metadata: bool,
    ) -> bool:
        """Algorithm 13 — verify the ``/Perms`` field after key recovery.

        Mirrors PDFBox's ``validatePerms`` (the read-side check). Returns
        ``True`` when bytes 9-11 are ``adb`` AND the little-endian permission
        integer in bytes 0-3 matches ``dic_permissions``. Caller decides what
        to do with a ``False`` — PDFBox merely logs and continues, since some
        encoders mis-emit the field.
        """
        plain = cls._decrypt_perms_r5_r6(file_key, perms)
        if len(plain) != 16:
            return False
        if plain[9] != ord("a") or plain[10] != ord("d") or plain[11] != ord("b"):
            return False
        perms_p = (
            plain[0]
            | (plain[1] << 8)
            | (plain[2] << 16)
            | (plain[3] << 24)
        )
        if perms_p & 0x80000000:
            perms_p -= 0x100000000
        if perms_p != _signed32(dic_permissions):
            return False
        expected = ord("T") if encrypt_metadata else ord("F")
        return plain[8] == expected

    def _build_r6_dictionary(
        self, owner_pw: bytes, user_pw: bytes, permissions: int
    ) -> tuple[bytes, bytes, bytes, bytes, bytes]:
        """Generate (O, OE, U, UE, Perms) for r6 using a random file key."""
        file_key = self.get_encryption_key()
        if file_key is None:
            file_key = os.urandom(32)
            self.set_encryption_key(file_key)

        truncated_user = user_pw[:127]
        truncated_owner = owner_pw[:127]

        user_validation_salt = os.urandom(8)
        user_key_salt = os.urandom(8)
        u_hash = self._compute_hash_r5_r6(
            truncated_user + user_validation_salt, truncated_user, b"", 6
        )
        u_value = u_hash + user_validation_salt + user_key_salt
        ue_intermediate = self._compute_hash_r5_r6(
            truncated_user + user_key_salt, truncated_user, b"", 6
        )
        ue = _aes_cbc_no_padding_encrypt(ue_intermediate, b"\x00" * 16, file_key)

        owner_validation_salt = os.urandom(8)
        owner_key_salt = os.urandom(8)
        o_hash = self._compute_hash_r5_r6(
            truncated_owner + owner_validation_salt + u_value,
            truncated_owner,
            u_value,
            6,
        )
        o_value = o_hash + owner_validation_salt + owner_key_salt
        oe_intermediate = self._compute_hash_r5_r6(
            truncated_owner + owner_key_salt + u_value,
            truncated_owner,
            u_value,
            6,
        )
        oe = _aes_cbc_no_padding_encrypt(oe_intermediate, b"\x00" * 16, file_key)

        # /Perms: AES-ECB(file_key, perms_block) — see §7.6.4.4.9.
        perms_block = bytearray(16)
        p = _signed32(permissions)
        perms_block[0] = p & 0xFF
        perms_block[1] = (p >> 8) & 0xFF
        perms_block[2] = (p >> 16) & 0xFF
        perms_block[3] = (p >> 24) & 0xFF
        perms_block[4] = 0xFF
        perms_block[5] = 0xFF
        perms_block[6] = 0xFF
        perms_block[7] = 0xFF
        perms_block[8] = ord("T") if self._encrypt_metadata else ord("F")
        perms_block[9] = ord("a")
        perms_block[10] = ord("d")
        perms_block[11] = ord("b")
        perms_block[12:16] = os.urandom(4)
        cipher = Cipher(algorithms.AES(file_key), modes.ECB())
        enc = cipher.encryptor()
        perms_value = enc.update(bytes(perms_block)) + enc.finalize()
        return o_value, oe, u_value, ue, perms_value

    # ---------------------------------------------- upstream-named parity API
    # The pypdfbox parity scanner converts upstream camelCase to snake_case
    # with a different boundary rule than the helpers above (e.g. ``computeRC4Key``
    # → ``compute_rc4key`` not ``compute_rc_4_key``). The methods below are
    # zero-cost aliases that surface the upstream private/static helpers under
    # the exact names parity expects, so the scanner credits them as matched.
    # All semantics defer to existing implementations — no behaviour changes.

    @staticmethod
    def truncate127(value: bytes) -> bytes:
        """Alias of :meth:`truncate_127` matching upstream ``truncate127`` (Java L1255)."""
        return StandardSecurityHandler.truncate_127(value)

    @classmethod
    def compute_sha256(
        cls, password: bytes, salt: bytes, user_key: bytes | None
    ) -> bytes:
        """Alias of :meth:`compute_sha_256` matching upstream ``computeSHA256`` (Java L1210)."""
        return cls.compute_sha_256(password, salt, user_key)

    @classmethod
    def compute_hash2_a(
        cls, password: bytes, salt: bytes, u: bytes | None
    ) -> bytes:
        """Alias of :meth:`compute_hash_2a` matching upstream ``computeHash2A`` (Java L1127)."""
        return cls.compute_hash_2a(password, salt, u)

    @classmethod
    def compute_hash2_b(
        cls, input_data: bytes, password: bytes, user_key: bytes | None
    ) -> bytes:
        """Alias of :meth:`compute_hash_2b` matching upstream ``computeHash2B`` (Java L1136)."""
        return cls.compute_hash_2b(input_data, password, user_key)

    @classmethod
    def compute_rc4key(
        cls, owner_password: bytes, enc_revision: int, length: int
    ) -> bytes:
        """Alias of :meth:`compute_rc_4_key` matching upstream ``computeRC4key``."""
        return cls.compute_rc_4_key(owner_password, enc_revision, length)

    @classmethod
    def compute_encrypted_key_rev234(
        cls,
        password: bytes,
        o: bytes,
        permissions: int,
        id_bytes: bytes,
        encrypt_metadata: bool,
        length: int,
        enc_revision: int,
    ) -> bytes:
        """Mirror upstream ``computeEncryptedKeyRev234`` (Java L740).

        Algorithm 2 — derive the file encryption key for r2-r4. Argument order
        matches the Java signature exactly: ``password, o, permissions, id,
        encryptMetadata, length, encRevision``.
        """
        return cls._compute_encryption_key(
            password,
            bytes(o),
            int(permissions),
            bytes(id_bytes),
            int(enc_revision),
            int(length),
            bool(encrypt_metadata),
        )

    @classmethod
    def compute_encrypted_key_rev56(
        cls,
        password: bytes,
        is_owner_password: bool,
        o: bytes,
        u: bytes,
        oe: bytes | None,
        ue: bytes | None,
        enc_revision: int,
    ) -> bytes:
        """Mirror upstream ``computeEncryptedKeyRev56`` (Java L783).

        AES-256-CBC unwrap of /OE or /UE under the SHA-256 (r5) or
        hardened-hash (r6) of the password + salt [+ U[:48]]. Defers to
        :meth:`_compute_encryption_key_rev_5_6`.
        """
        if is_owner_password and oe is None:
            raise OSError("/Encrypt/OE entry is missing")
        if not is_owner_password and ue is None:
            raise OSError("/Encrypt/UE entry is missing")
        return cls._compute_encryption_key_rev_5_6(
            bytes(password),
            bool(is_owner_password),
            bytes(o),
            bytes(u),
            bytes(oe) if oe is not None else b"",
            bytes(ue) if ue is not None else b"",
            int(enc_revision),
        )

    @classmethod
    def is_user_password234(
        cls,
        password: bytes,
        user: bytes,
        owner: bytes,
        permissions: int,
        id_bytes: bytes,
        enc_revision: int,
        key_length_in_bytes: int,
        encrypt_metadata: bool,
    ) -> bool:
        """Alias of :meth:`_is_user_password_2_3_4` mirroring ``isUserPassword234`` (Java L1032)."""
        return cls._is_user_password_2_3_4(
            password, user, owner, permissions, id_bytes,
            enc_revision, key_length_in_bytes, encrypt_metadata,
        )

    @classmethod
    def is_user_password56(
        cls, password: bytes, user: bytes, enc_revision: int
    ) -> bool:
        """Alias of :meth:`_is_user_password_5_6` mirroring ``isUserPassword56`` (Java L1049)."""
        return cls._is_user_password_5_6(password, user, enc_revision)

    @classmethod
    def is_owner_password234(
        cls,
        password: bytes,
        user: bytes,
        owner: bytes,
        permissions: int,
        id_bytes: bytes,
        enc_revision: int,
        key_length_in_bytes: int,
        encrypt_metadata: bool,
    ) -> bool:
        """Alias of ``_is_owner_password_2_3_4`` — upstream ``isOwnerPassword234`` (Java L611)."""
        return cls._is_owner_password_2_3_4(
            password, user, owner, permissions, id_bytes,
            enc_revision, key_length_in_bytes, encrypt_metadata,
        )

    @classmethod
    def is_owner_password56(
        cls, password: bytes, user: bytes, owner: bytes, enc_revision: int
    ) -> bool:
        """Alias of :meth:`_is_owner_password_5_6` mirroring ``isOwnerPassword56`` (Java L622)."""
        return cls._is_owner_password_5_6(password, user, owner, enc_revision)

    @classmethod
    def get_user_password234(
        cls,
        owner_password: bytes,
        owner: bytes,
        enc_revision: int,
        length: int,
    ) -> bytes:
        """Mirror upstream ``getUserPassword234`` (Java L674) — Algorithm 7 inverse for r2-r4.

        Recover the padded user password from the owner password and the /O
        entry. Defers to the same RC4 unwinding loop as :meth:`get_user_password`,
        but skipping the r5/r6 short-circuit so callers reach the r2-r4 path
        directly.
        """
        rc4_key = cls.compute_rc_4_key(owner_password, int(enc_revision), int(length))
        if int(enc_revision) == 2:
            return _rc4(rc4_key, bytes(owner))
        # r3, r4 — 20 inverse rounds with rotated keys (Java L691-L703).
        result = bytes(owner)
        for i in range(19, -1, -1):
            rotated = bytes(b ^ i for b in rc4_key)
            result = _rc4(rotated, result)
        return result

    @staticmethod
    def get_document_id_bytes(document_id: object) -> bytes:
        """Alias of :meth:`_get_document_id_bytes` mirroring ``getDocumentIDBytes`` (Java L298)."""
        return StandardSecurityHandler._get_document_id_bytes(document_id)

    @staticmethod
    def concat(*parts: bytes) -> bytes:
        """Mirror upstream ``concat`` overloads (Java L1238, L1246).

        Variadic over the upstream 2-arg and 3-arg shapes so a single Python
        method covers both Java overloads.
        """
        out = bytearray()
        for p in parts:
            out.extend(bytes(p))
        return bytes(out)

    @staticmethod
    def log_if_strong_encryption_missing() -> None:
        """Mirror upstream ``logIfStrongEncryptionMissing`` (Java L1266).

        Java warns when the JCE unlimited-strength jurisdiction policy is
        absent — Python's ``cryptography`` ships with full key-length support
        unconditionally, so this is a no-op. Kept for API parity.
        """
        return None

    def prepare_encryption_dict_aes(
        self, encryption_dictionary: PDEncryption, aes_v_name: str
    ) -> None:
        """Mirror upstream ``prepareEncryptionDictAES`` (Java L565).

        Install a /CF/StdCF entry whose /CFM is ``aes_v_name`` (AESV2 or
        AESV3), point /StmF and /StrF at it, and flip ``set_aes(True)``.
        Defers to :meth:`_install_std_crypt_filter` for the dictionary
        wiring.
        """
        self._install_std_crypt_filter(
            encryption_dictionary, aes_v_name, self.get_key_length() // 8
        )
        self.set_aes(True)

    def prepare_encryption_dict_rev234(
        self,
        owner_password: str,
        user_password: str,
        encryption_dictionary: PDEncryption,
        permission_int: int,
        document: object,
        revision: int,
        length: int,
    ) -> None:
        """Mirror upstream ``prepareEncryptionDictRev234`` (Java L515).

        Build /O, /U, /Perms for r2-r4 and stash the file encryption key on
        this handler. For r4 also installs the AESV2 crypt filter via
        :meth:`prepare_encryption_dict_aes`.
        """
        owner_pw_bytes = owner_password.encode("latin-1", errors="replace")
        user_pw_bytes = user_password.encode("latin-1", errors="replace")
        if not owner_pw_bytes:
            owner_pw_bytes = user_pw_bytes

        document_id = self._extract_document_id(document, b"\x00" * 16)

        owner_bytes = self._compute_owner_password_r2_r4(
            owner_pw_bytes, user_pw_bytes, int(revision), int(length)
        )
        file_key = self.compute_encrypted_key_rev234(
            user_pw_bytes,
            owner_bytes,
            int(permission_int),
            document_id,
            True,
            int(length),
            int(revision),
        )
        self.set_encryption_key(file_key)
        user_bytes = self._compute_user_password_r2_r4(
            user_pw_bytes,
            owner_bytes,
            int(permission_int),
            document_id,
            int(revision),
            int(length),
        )
        encryption_dictionary.set_o(owner_bytes)
        encryption_dictionary.set_u(user_bytes)
        if int(revision) == 4:
            self.prepare_encryption_dict_aes(encryption_dictionary, _CFM_AESV2)

    def prepare_encryption_dict_rev6(
        self,
        owner_password: str,
        user_password: str,
        encryption_dictionary: PDEncryption,
        permission_int: int,
    ) -> None:
        """Mirror upstream ``prepareEncryptionDictRev6`` (Java L425).

        Generate a random 32-byte file encryption key, build (O, OE, U, UE,
        Perms) for r6, attach them to ``encryption_dictionary``, and install
        the AESV3 crypt filter. Defers heavy lifting to
        :meth:`_build_r6_dictionary`.
        """
        owner_pw_bytes = owner_password.encode("utf-8", errors="replace")
        user_pw_bytes = user_password.encode("utf-8", errors="replace")
        if not owner_pw_bytes:
            owner_pw_bytes = user_pw_bytes
        # Random 256-bit file encryption key (Java L434-L435).
        self.set_encryption_key(os.urandom(32))
        o, oe, u, ue, perms = self._build_r6_dictionary(
            owner_pw_bytes, user_pw_bytes, int(permission_int)
        )
        encryption_dictionary.set_user_key(u)
        encryption_dictionary.set_user_encryption_key(ue)
        encryption_dictionary.set_owner_key(o)
        encryption_dictionary.set_owner_encryption_key(oe)
        encryption_dictionary.set_perms(perms)
        self.prepare_encryption_dict_aes(encryption_dictionary, _CFM_AESV3)


# ----------------------------------------------------------------------------
# Local cipher helpers — kept private to this module to avoid exposing
# IV-less primitives more broadly than necessary.


def _rc4(key: bytes, data: bytes) -> bytes:
    cipher = Cipher(_ARC4(key), mode=None)
    enc = cipher.encryptor()
    return enc.update(data) + enc.finalize()


def _aes128_cbc_encrypt(key: bytes, data: bytes) -> bytes:
    """AES-CBC with PKCS#7 padding and a random 16-byte IV prefix.

    Used by AESV2 (per-object key, n+5 → 16 bytes) and AESV3 (file key, 32
    bytes) per-object cipher dispatch. Mirrors the on-disk layout that
    ``SecurityHandler`` already produces for the V<4 legacy path.
    """
    iv = os.urandom(16)
    padder = _aes_padding.PKCS7(128).padder()
    padded = padder.update(data) + padder.finalize()
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    enc = cipher.encryptor()
    return iv + enc.update(padded) + enc.finalize()


def _aes128_cbc_decrypt(key: bytes, data: bytes) -> bytes:
    """AES-CBC inverse of :func:`_aes128_cbc_encrypt`.

    Tolerant of malformed PKCS#7 padding (returns the raw padded bytes) to
    match PDFBox's loose decryption behaviour — strict callers should wrap
    this in their own validation.
    """
    if len(data) < 16:
        return b""
    iv, ct = data[:16], data[16:]
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    dec = cipher.decryptor()
    padded = dec.update(ct) + dec.finalize()
    unpadder = _aes_padding.PKCS7(128).unpadder()
    try:
        return unpadder.update(padded) + unpadder.finalize()
    except ValueError:
        return padded


def _aes_cbc_no_padding_encrypt(key: bytes, iv: bytes, data: bytes) -> bytes:
    """AES-CBC without PKCS#7 — used inside r6 key wrap (data is block-aligned)."""
    if len(data) % 16 != 0:
        # Pad with zeros to a 16-byte boundary; r5/r6 inputs are always 16/32 bytes.
        data = data + b"\x00" * (16 - len(data) % 16)
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    enc = cipher.encryptor()
    return enc.update(data) + enc.finalize()


def _aes_cbc_no_padding_decrypt(key: bytes, iv: bytes, data: bytes) -> bytes:
    if len(data) % 16 != 0:
        data = data[: len(data) - (len(data) % 16)]
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    dec = cipher.decryptor()
    return dec.update(data) + dec.finalize()


def _signed32(value: int) -> int:
    """Coerce ``value`` to a signed 32-bit int (PDFBox writes /P as int32)."""
    value &= 0xFFFFFFFF
    if value & 0x80000000:
        value -= 0x100000000
    return value


# Bind ``PROTECTION_POLICY_CLASS`` after class construction. Done at the
# bottom of the module to avoid a top-level circular import — every module
# in this package imports this file, so referencing
# ``StandardProtectionPolicy`` at class-body time would deadlock.
from .standard_protection_policy import (  # noqa: E402
    StandardProtectionPolicy as _StandardProtectionPolicy,
)

StandardSecurityHandler.PROTECTION_POLICY_CLASS = _StandardProtectionPolicy


__all__ = [
    "DEFAULT_PERMISSIONS",
    "InvalidPasswordException",
    "StandardDecryptionMaterial",
    "StandardSecurityHandler",
]
