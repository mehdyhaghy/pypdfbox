"""Abstract base for PDF security handlers.

Mirrors ``org.apache.pdfbox.pdmodel.encryption.SecurityHandler``. The base
provides per-object key derivation (PDF 32000-1 §7.6.3.2) plus the
RC4 / AES dispatch used by string and stream codecs. Concrete subclasses
implement password validation (``prepare_for_decryption``) and write-side
preparation (``prepare_document``).
"""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from cryptography.hazmat.primitives import padding as _padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

try:
    # cryptography >= 43 moved RC4 here; PDFBox r2-r4 still need it for
    # legacy file decryption.
    from cryptography.hazmat.decrepit.ciphers.algorithms import ARC4 as _ARC4
except ImportError:  # pragma: no cover — older cryptography releases
    from cryptography.hazmat.primitives.ciphers.algorithms import ARC4 as _ARC4

if TYPE_CHECKING:
    from .access_permission import AccessPermission
    from .pd_encryption import PDEncryption


# AES salt used by V=4 / AESV2 per-object key derivation (PDF 32000-1 §7.6.3.2).
_AES_SALT = b"sAlT"


class SecurityHandler(ABC):
    """Lite port of ``SecurityHandler``.

    Holds the parsed file-encryption key plus per-object key derivation and
    string / stream cipher dispatch. RC4 and AES-CBC primitives come from the
    ``cryptography`` package — we never roll our own block cipher.
    """

    def __init__(self) -> None:
        self._encryption_key: bytes | None = None
        self._key_length: int = 40  # bits
        self._revision: int = 0
        self._version: int = 0
        self._aes: bool = False
        self._decrypt_metadata: bool = True
        self._current_access_permission: AccessPermission | None = None
        self._decryption_material: object | None = None

    # ------------------------------------------------------------------ state

    def get_encryption_key(self) -> bytes | None:
        return self._encryption_key

    def set_encryption_key(self, key: bytes) -> None:
        self._encryption_key = bytes(key)

    def get_key_length(self) -> int:
        return self._key_length

    def set_key_length(self, key_length: int) -> None:
        self._key_length = int(key_length)

    def get_revision(self) -> int:
        return self._revision

    def set_revision(self, revision: int) -> None:
        self._revision = int(revision)

    def get_version(self) -> int:
        return self._version

    def set_version(self, version: int) -> None:
        self._version = int(version)

    def is_aes(self) -> bool:
        return self._aes

    def set_aes(self, b: bool) -> None:
        self._aes = bool(b)

    # ------------------------------------------------------- access permission

    def get_current_access_permission(self) -> AccessPermission | None:
        """Return the access permission resolved by ``prepare_for_decryption``.

        ``None`` until a successful decryption has populated it. Mirrors
        ``SecurityHandler#getCurrentAccessPermission`` upstream.
        """
        return self._current_access_permission

    def set_current_access_permission(self, perm: AccessPermission) -> None:
        self._current_access_permission = perm

    # --------------------------------------------------------- material access

    def get_decryption_material(self) -> object | None:
        """Return the decryption material supplied to ``prepare_for_decryption``.

        Stored opaquely so this base remains agnostic to standard vs.
        public-key flows.
        """
        return self._decryption_material

    def set_decryption_material(self, material: object) -> None:
        self._decryption_material = material

    # ----------------------------------------------------- metadata decrypt flag

    def is_decrypt_metadata(self) -> bool:
        """Whether document metadata streams should be decrypted.

        Some upstream variants expose ``isDecryptMetadata`` in addition to
        the encryption-dictionary flag. Defaults to ``True``.
        """
        return self._decrypt_metadata

    def set_decrypt_metadata(self, b: bool) -> None:
        self._decrypt_metadata = bool(b)

    # ------------------------------------------------------------ subclass API

    @abstractmethod
    def prepare_for_decryption(
        self,
        encryption: PDEncryption,
        document_id: bytes,
        decryption_material: object,
    ) -> None:
        """Validate decryption material and populate ``encryption_key``."""

    @abstractmethod
    def prepare_document(self, document: object) -> None:
        """Populate the encryption dictionary on ``document`` for write."""

    # ------------------------------------------------------------ object key

    def compute_object_key(self, obj_num: int, gen_num: int) -> bytes:
        """Return the per-object key per PDF 32000-1 §7.6.3.2.

        For revisions <= 4 the per-object key is MD5(file_key || obj_num[0:3]
        || gen_num[0:2] [|| "sAlT" if AES]) truncated to min(n+5, 16) bytes,
        where n is the file-key length in bytes.

        For revisions >= 5 (V >= 5) the file-encryption key is used directly
        for every object, no salting.
        """
        if self._encryption_key is None:
            raise ValueError(
                "encryption_key not set — call prepare_for_decryption first"
            )

        if self._revision >= 5:
            return self._encryption_key

        n = len(self._encryption_key)
        md5 = hashlib.md5(usedforsecurity=False)
        md5.update(self._encryption_key)
        md5.update(
            bytes(
                [
                    obj_num & 0xFF,
                    (obj_num >> 8) & 0xFF,
                    (obj_num >> 16) & 0xFF,
                    gen_num & 0xFF,
                    (gen_num >> 8) & 0xFF,
                ]
            )
        )
        if self._aes:
            md5.update(_AES_SALT)
        digest = md5.digest()
        return digest[: min(n + 5, 16)]

    # ------------------------------------------------------- string encoding

    def decrypt_string(self, s: bytes, obj_num: int, gen_num: int) -> bytes:
        return self._decrypt(s, obj_num, gen_num)

    def encrypt_string(self, s: bytes, obj_num: int, gen_num: int) -> bytes:
        return self._encrypt(s, obj_num, gen_num)

    def decrypt_stream(self, data: bytes, obj_num: int, gen_num: int) -> bytes:
        return self._decrypt(data, obj_num, gen_num)

    def encrypt_stream(self, data: bytes, obj_num: int, gen_num: int) -> bytes:
        return self._encrypt(data, obj_num, gen_num)

    # ----------------------------------------------- generic data convenience

    def decrypt_data(
        self, input_stream: object, obj_num: int, gen_num: int
    ) -> bytes:
        """Decrypt arbitrary stream-like input.

        Mirrors ``SecurityHandler#decryptData`` — accepts either a ``bytes``
        payload or any object with a ``read()`` method (file-like). Returns
        the decrypted bytes.
        """
        data = self._coerce_to_bytes(input_stream)
        return self._decrypt(data, obj_num, gen_num)

    def encrypt_data(
        self, input_stream: object, obj_num: int, gen_num: int
    ) -> bytes:
        """Encrypt arbitrary stream-like input. See :meth:`decrypt_data`."""
        data = self._coerce_to_bytes(input_stream)
        return self._encrypt(data, obj_num, gen_num)

    @staticmethod
    def _coerce_to_bytes(input_stream: object) -> bytes:
        if isinstance(input_stream, (bytes, bytearray, memoryview)):
            return bytes(input_stream)
        read = getattr(input_stream, "read", None)
        if callable(read):
            return bytes(read())
        raise TypeError(
            "input_stream must be bytes-like or a file-like object with read()"
        )

    # -------------------------------------------- subclass-override placeholders

    def compute_encrypted_key(
        self,
        password: bytes,
        o: bytes | None = None,
        u: bytes | None = None,
        oe: bytes | None = None,
        ue: bytes | None = None,
        permissions: int | None = None,
        document_id: bytes | None = None,
        revision: int | None = None,
        length_in_bits: int | None = None,
        encrypt_metadata: bool | None = None,
        is_owner_password: bool = False,
    ) -> bytes:
        """Compute the file-encryption key from a password.

        Placeholder on the base class — concrete handlers (e.g. the standard
        security handler) implement the per-revision algorithms.
        """
        raise NotImplementedError(
            "compute_encrypted_key must be implemented by a concrete "
            "SecurityHandler subclass"
        )

    def compute_user_password(
        self,
        password: bytes,
        o: bytes | None = None,
        permissions: int | None = None,
        document_id: bytes | None = None,
        revision: int | None = None,
        length_in_bits: int | None = None,
        encrypt_metadata: bool | None = None,
    ) -> bytes:
        """Compute the /U entry from a password. Subclass override."""
        raise NotImplementedError(
            "compute_user_password must be implemented by a concrete "
            "SecurityHandler subclass"
        )

    def compute_owner_password(
        self,
        owner_password: bytes,
        user_password: bytes,
        revision: int | None = None,
        length_in_bits: int | None = None,
    ) -> bytes:
        """Compute the /O entry from owner+user passwords. Subclass override."""
        raise NotImplementedError(
            "compute_owner_password must be implemented by a concrete "
            "SecurityHandler subclass"
        )

    # ------------------------------------------------------------ internals

    def _decrypt(self, data: bytes, obj_num: int, gen_num: int) -> bytes:
        if self._revision >= 5:
            # AES-256 with the file-encryption key directly.
            return _aes_cbc_decrypt(self._encryption_key or b"", data)
        key = self.compute_object_key(obj_num, gen_num)
        if self._aes:
            return _aes_cbc_decrypt(key, data)
        return _rc4(key, data)

    def _encrypt(self, data: bytes, obj_num: int, gen_num: int) -> bytes:
        if self._revision >= 5:
            return _aes_cbc_encrypt(self._encryption_key or b"", data)
        key = self.compute_object_key(obj_num, gen_num)
        if self._aes:
            return _aes_cbc_encrypt(key, data)
        return _rc4(key, data)


# ----------------------------------------------------------------------------
# Cipher helpers — thin wrappers around ``cryptography`` so the call sites stay
# readable and we have one place to centralize PKCS#7 + 16-byte IV plumbing.


def _rc4(key: bytes, data: bytes) -> bytes:
    cipher = Cipher(_ARC4(key), mode=None)
    enc = cipher.encryptor()
    return enc.update(data) + enc.finalize()


def _aes_cbc_decrypt(key: bytes, data: bytes) -> bytes:
    if len(data) < 16:
        return b""
    iv, ct = data[:16], data[16:]
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    dec = cipher.decryptor()
    padded = dec.update(ct) + dec.finalize()
    unpadder = _padding.PKCS7(128).unpadder()
    try:
        return unpadder.update(padded) + unpadder.finalize()
    except ValueError:
        # Malformed padding — return raw to mirror PDFBox's tolerant behaviour
        # (it logs and returns what it could decrypt). Strict callers should
        # wrap this in their own validation.
        return padded


def _aes_cbc_encrypt(key: bytes, data: bytes) -> bytes:
    import os

    iv = os.urandom(16)
    padder = _padding.PKCS7(128).padder()
    padded = padder.update(data) + padder.finalize()
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    enc = cipher.encryptor()
    return iv + enc.update(padded) + enc.finalize()


__all__ = ["SecurityHandler"]
