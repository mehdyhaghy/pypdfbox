"""``/Filter /Standard`` security handler covering revisions 2 through 6.

Mirrors ``org.apache.pdfbox.pdmodel.encryption.StandardSecurityHandler``. Two
families are implemented:

* **Revisions 2-4** — RC4-40/128 and AES-128 with the legacy padding-based
  key derivation in PDF 32000-1 §7.6.4.3 / §7.6.4.4.
* **Revisions 5-6** — AES-256 with the SHA-2 / AES-key-wrap construction in
  PDF 32000-2 §7.6.4.4.6 onwards. The hardened r6 hash (algorithm 2.B from
  §7.6.4.3.4) is included.

This is the *lite* port: it implements the password / key derivation paths
needed to read and write encrypted documents, but does not yet model
``/Recipients`` (public-key handlers), ``/CF`` per-stream crypt-filter
selection, or strict per-revision key-length validation. Those are tracked
in ``CHANGES.md``.
"""

from __future__ import annotations

import hashlib
import os
import struct
from typing import TYPE_CHECKING

from cryptography.hazmat.primitives import padding as _padding  # noqa: F401
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

try:
    from cryptography.hazmat.decrepit.ciphers.algorithms import ARC4 as _ARC4
except ImportError:  # pragma: no cover
    from cryptography.hazmat.primitives.ciphers.algorithms import ARC4 as _ARC4

from .security_handler import SecurityHandler

if TYPE_CHECKING:
    from .pd_encryption import PDEncryption


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

    # ------------------------------------------------------------ accessors

    def get_permissions(self) -> int:
        return self._permissions

    def is_encrypt_metadata(self) -> bool:
        return self._encrypt_metadata

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
        if stm_f is None or stm_f == "Identity":
            return False
        # Authoritative path: look up the named crypt filter and read /CFM.
        crypt_filter = encryption.get_crypt_filter_dictionary(stm_f)
        if crypt_filter is not None:
            cfm = crypt_filter.get_cfm()
            if cfm is not None:
                return cfm in ("AESV2", "AESV3")
        # Fallback for legacy writers that put the algorithm directly in /StmF
        # without a matching /CF entry.
        return stm_f in ("AESV2", "AESV3")

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

        # Attach the encryption dictionary to the document if it exposes the
        # standard PDFBox setter.
        if hasattr(document, "set_encryption_dictionary"):
            document.set_encryption_dictionary(encryption)

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
        64-iteration AES + SHA-2 round is applied.
        """
        k = hashlib.sha256(input_data).digest()
        if revision == 5:
            return k

        round_no = 0
        last_byte = 0
        while round_no < 64 or last_byte > round_no - 32:
            k1 = (password + k + user_key) * 64
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
