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
import logging
import os
import struct
from typing import TYPE_CHECKING

_LOG = logging.getLogger(__name__)

from cryptography.hazmat.primitives import padding as _aes_padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

try:
    from cryptography.hazmat.decrepit.ciphers.algorithms import ARC4 as _ARC4
except ImportError:  # pragma: no cover
    from cryptography.hazmat.primitives.ciphers.algorithms import ARC4 as _ARC4

from .security_handler import SecurityHandler

if TYPE_CHECKING:
    from .pd_encryption import PDEncryption


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


class PDInvalidPasswordException(OSError):
    """Raised when neither owner nor user password validates."""

    def __init__(
        self,
        message: str = "Cannot decrypt PDF, the password is incorrect",
    ) -> None:
        super().__init__(message)


class StandardDecryptionMaterial:
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

    def get_password_str(self) -> str | None:
        if self._password is None:
            return None
        if isinstance(self._password, bytes):
            return self._password.decode("latin-1", errors="replace")
        return self._password


class StandardSecurityHandler(SecurityHandler):
    """Concrete handler for ``/Filter /Standard`` revisions 2 through 6."""

    FILTER = "Standard"

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

    # ----------------------------------------------------- upstream parity

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
    def compute_user_password(
        cls,
        password: bytes,
        owner_entry: bytes,
        permissions: int,
        document_id: bytes,
        revision: int,
        key_len_bytes: int,
        encrypt_metadata: bool = True,
    ) -> bytes:
        """Algorithm 4/5 — derive the /U entry. Public alias."""
        return cls._compute_user_password_r2_r4(
            password,
            owner_entry,
            permissions,
            document_id,
            revision,
            key_len_bytes,
        )

    @classmethod
    def compute_owner_password(
        cls,
        owner_password: bytes,
        user_password: bytes,
        revision: int,
        key_len_bytes: int,
    ) -> bytes:
        """Algorithm 3 — derive the /O entry. Public alias."""
        return cls._compute_owner_password_r2_r4(
            owner_password, user_password, revision, key_len_bytes
        )

    @classmethod
    def compute_encrypted_key(
        cls,
        password: bytes,
        o: bytes,
        permissions: int,
        document_id: bytes,
        revision: int,
        key_len_bytes: int,
        encrypt_metadata: bool = True,
    ) -> bytes:
        """Algorithm 2 — derive the file encryption key. Public alias."""
        return cls._compute_encryption_key(
            password,
            o,
            permissions,
            document_id,
            revision,
            key_len_bytes,
            encrypt_metadata,
        )

    @classmethod
    def is_user_password(
        cls,
        password: bytes | str,
        encryption: PDEncryption,
        document_id: bytes,
    ) -> bool:
        """Return True if ``password`` validates as the user password.

        Mirrors PDFBox ``isUserPassword``. Supports r2-r4 via the legacy
        validation path and r5/r6 via the SHA-256 / hardened-hash path.
        """
        pw = password.encode("latin-1", errors="replace") if isinstance(password, str) else bytes(password or b"")
        revision = int(encryption.get_revision())
        if revision >= 5:
            u = encryption.get_u() or b""
            if len(u) < 40:
                return False
            user_validation_salt = u[32:40]
            return cls._compute_hash_r5_r6(
                pw[:127] + user_validation_salt, pw[:127], b"", revision
            ) == u[:32]
        key_length_bits = int(
            encryption.get_length() or (40 if revision < 3 else 128)
        )
        key_len_bytes = key_length_bits // 8
        encrypt_metadata = bool(encryption.is_encrypt_meta_data())
        return cls._compute_encryption_key_via_user_password(
            pw,
            encryption.get_o() or b"",
            encryption.get_u() or b"",
            int(encryption.get_p()),
            document_id,
            revision,
            key_len_bytes,
            encrypt_metadata,
        ) is not None

    @classmethod
    def is_owner_password(
        cls,
        password: bytes | str,
        encryption: PDEncryption,
        document_id: bytes,
    ) -> bool:
        """Return True if ``password`` validates as the owner password.

        Mirrors PDFBox ``isOwnerPassword``.
        """
        pw = password.encode("latin-1", errors="replace") if isinstance(password, str) else bytes(password or b"")
        revision = int(encryption.get_revision())
        if revision >= 5:
            o = encryption.get_o() or b""
            u = encryption.get_u() or b""
            if len(o) < 40 or len(u) < 48:
                return False
            owner_validation_salt = o[32:40]
            return cls._compute_hash_r5_r6(
                pw[:127] + owner_validation_salt + u[:48], pw[:127], u[:48], revision
            ) == o[:32]
        key_length_bits = int(
            encryption.get_length() or (40 if revision < 3 else 128)
        )
        key_len_bytes = key_length_bits // 8
        encrypt_metadata = bool(encryption.is_encrypt_meta_data())
        return cls._compute_encryption_key_via_owner_password(
            pw,
            encryption.get_o() or b"",
            encryption.get_u() or b"",
            int(encryption.get_p()),
            document_id,
            revision,
            key_len_bytes,
            encrypt_metadata,
        ) is not None

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
        if cfm == _CFM_IDENTITY or cfm == _CFM_NONE:
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
        if cfm == _CFM_IDENTITY or cfm == _CFM_NONE:
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
        document_id: bytes,
        decryption_material: object,
    ) -> None:
        if not isinstance(decryption_material, StandardDecryptionMaterial):
            raise TypeError(
                "StandardSecurityHandler requires StandardDecryptionMaterial"
            )

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

        password = decryption_material.get_password() or b""
        o = encryption.get_o()
        u = encryption.get_u()

        if revision >= 5:
            oe = encryption.get_oe()
            ue = encryption.get_ue()
            perms = encryption.get_perms()
            key = self._compute_encryption_key_r5_r6(
                password, o, u, oe, ue, perms, revision
            )
            if key is None:
                raise PDInvalidPasswordException()
            self.set_encryption_key(key)
            # Algorithm 13 — verify /Perms. Upstream merely warns on mismatch
            # since some encoders mis-emit the field; we do the same so we
            # stay tolerant of buggy producers (PDFBox parity).
            if perms is not None and len(perms) == 16:
                if not self._validate_perms_r5_r6(
                    key, perms, self._permissions, self._encrypt_metadata
                ):
                    _LOG.warning(
                        "Verification of /Perms failed — using /P from "
                        "the encryption dictionary"
                    )
            return

        # Revisions 2-4: try owner password first, then user password.
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
            return

        raise PDInvalidPasswordException()

    # ----------------------------------------------------------- write path

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
            revision, version = 2, 1
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
                user_pw, o, permissions, document_id, revision, key_len_bits // 8
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
            for _ in range(50):
                digest = hashlib.md5(digest, usedforsecurity=False).digest()
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
    ) -> bytes:
        """PDF 32000-1 §7.6.4.4.3-.4 algorithms 4 and 5 — produce /U entry."""
        file_key = cls._compute_encryption_key(
            password,
            o,
            permissions,
            document_id,
            revision,
            key_len_bytes,
            encrypt_metadata=True,
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
            for _ in range(50):
                digest = hashlib.md5(digest, usedforsecurity=False).digest()
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


__all__ = [
    "DEFAULT_PERMISSIONS",
    "PDInvalidPasswordException",
    "StandardDecryptionMaterial",
    "StandardSecurityHandler",
]
