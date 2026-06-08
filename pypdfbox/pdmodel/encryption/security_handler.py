"""Abstract base for PDF security handlers.

Mirrors ``org.apache.pdfbox.pdmodel.encryption.SecurityHandler``. The base
provides per-object key derivation (PDF 32000-1 §7.6.3.2) plus the
RC4 / AES dispatch used by string and stream codecs. Concrete subclasses
implement password validation (``prepare_for_decryption``) and write-side
preparation (``prepare_document``).
"""

from __future__ import annotations

import contextlib
import hashlib
import io as _io
import logging
import os as _os
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

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

_LOG = logging.getLogger(__name__)


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
        self._stream_filter_name: object | None = None
        self._string_filter_name: object | None = None
        self._custom_secure_random: Any = None
        # Base-level protection policy slot. Subclasses may shadow this with
        # their own ``_protection_policy`` attribute (both standard and
        # public-key handlers do); the helpers below honour either.
        self._protection_policy: object | None = None

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

    # ---------------------------------------------------------- filter names

    def set_string_filter_name(self, name: object) -> None:
        """Mirror ``SecurityHandler#setStringFilterName`` (line 159)."""
        self._string_filter_name = name

    def get_string_filter_name(self) -> object | None:
        """Return the configured string filter name (parity accessor)."""
        return self._string_filter_name

    def set_stream_filter_name(self, name: object) -> None:
        """Mirror ``SecurityHandler#setStreamFilterName`` (line 169)."""
        self._stream_filter_name = name

    def get_stream_filter_name(self) -> object | None:
        """Return the configured stream filter name (parity accessor)."""
        return self._stream_filter_name

    # -------------------------------------------------- secure-random override

    def set_custom_secure_random(self, rng: Any) -> None:
        """Mirror ``SecurityHandler#setCustomSecureRandom`` (line 179).

        The supplied object is used by AES IV generation in place of the
        default ``os.urandom``. It must expose either a ``read(n)``-style
        interface or a callable ``__call__(n)`` returning ``n`` bytes; a
        Python ``random.Random`` is also accepted via ``randbytes``.
        """
        self._custom_secure_random = rng

    def get_secure_random(self) -> Any:
        """Return the active secure-random source.

        Mirrors the upstream private accessor (line 436): falls back to
        ``os.urandom``-backed default when no custom RNG is set.
        """
        if self._custom_secure_random is not None:
            return self._custom_secure_random
        return _DEFAULT_SECURE_RANDOM

    # ----------------------------------------------------- protection policy

    def has_protection_policy(self) -> bool:
        """Mirror ``SecurityHandler#hasProtectionPolicy`` (line 804)."""
        return self._protection_policy is not None

    def get_protection_policy(self) -> object | None:
        """Mirror ``SecurityHandler#getProtectionPolicy`` (line 814)."""
        return self._protection_policy

    def set_protection_policy(self, policy: object | None) -> None:
        """Mirror ``SecurityHandler#setProtectionPolicy`` (line 823)."""
        self._protection_policy = policy

    # ---------------------------------------------------- /V version compute

    def compute_version_number(self) -> int:
        """Mirror ``SecurityHandler#computeVersionNumber`` (line 858).

        Picks a ``/V`` value from the configured key length plus the
        attached protection policy's AES preference:

        - ``key_length == 40``                       → 1 (RC4-40)
        - ``key_length == 128 && policy.preferAES``  → 4 (AES-128)
        - ``key_length == 256``                      → 5 (AES-256)
        - otherwise                                  → 2 (RC4-128)
        """
        if self._key_length == 40:
            return 1
        if self._key_length == 128:
            policy = self._protection_policy
            prefer_aes = False
            if policy is not None:
                getter = getattr(policy, "is_prefer_aes", None) or getattr(
                    policy, "is_preferred_aes", None
                )
                if callable(getter):
                    try:
                        prefer_aes = bool(getter())
                    except TypeError:
                        prefer_aes = False
            if prefer_aes:
                return 4
        if self._key_length == 256:
            return 5
        return 2

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

    def prepare_document_for_encryption(self, document: object) -> None:
        """Mirror ``SecurityHandler#prepareDocumentForEncryption`` (line 191).

        Default delegates to :meth:`prepare_document`. Concrete handlers
        (standard / public-key) override this with their algorithm-specific
        pre-flight; the bridge here keeps base-only callers (and the
        upstream parity surface) working with a single override.
        """
        self.prepare_document(document)

    # ------------------------------------------------------------ object key

    def compute_object_key(
        self, obj_num: int, gen_num: int, aes: bool | None = None
    ) -> bytes:
        """Return the per-object key per PDF 32000-1 §7.6.3.2.

        For revisions <= 4 the per-object key is MD5(file_key || obj_num[0:3]
        || gen_num[0:2] [|| "sAlT" if AES]) truncated to min(n+5, 16) bytes,
        where n is the file-key length in bytes.

        For revisions >= 5 (V >= 5) the file-encryption key is used directly
        for every object, no salting.

        ``aes`` overrides the handler-wide :attr:`_aes` flag for this one
        derivation. Mixed crypt-filter routing (e.g. /StmF /Identity but
        /StrF /StdCF AESV2) means the AES-salt rule cannot be read off the
        single document-level flag: an AESV2-routed object always needs the
        ``sAlT`` suffix even when the document's *default* filter is not AES.
        The V4/V5 dispatch passes ``aes=True`` for AESV2 and ``aes=False``
        for V2/RC4 so each object is keyed correctly regardless of the
        default-filter flag. Left ``None`` it falls back to :attr:`_aes`,
        preserving the legacy single-algorithm behaviour.
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
        use_aes = self._aes if aes is None else aes
        if use_aes:
            md5.update(_AES_SALT)
        digest = md5.digest()
        return digest[: min(n + 5, 16)]

    # Upstream alias — ``calcFinalKey`` is the Java-internal name (line 248).
    def calc_final_key(self, obj_num: int, gen_num: int) -> bytes:
        """Alias for :meth:`compute_object_key` matching upstream naming."""
        return self.compute_object_key(obj_num, gen_num)

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

        Upstream Java declares this exclusively on
        ``StandardSecurityHandler``. Subclasses that derive keys from
        passwords (currently only :class:`StandardSecurityHandler`)
        override this method with their concrete algorithm; non-password
        handlers (e.g. :class:`PublicKeySecurityHandler`) inherit the
        ``TypeError`` raised here — they wrap the file key in a recipient
        list instead. The base intentionally does not delegate to
        :class:`StandardSecurityHandler`: Python method dispatch already
        routes ``self.compute_encrypted_key(...)`` to the subclass when
        ``self`` is a :class:`StandardSecurityHandler`, so any fallthrough
        delegation here would be structurally unreachable.
        """
        raise TypeError(
            f"{type(self).__name__} does not derive keys from a password;"
            " call compute_encrypted_key on a StandardSecurityHandler."
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
        """Compute the /U entry from a password.

        Routes to the standard handler's algorithm 4/5. Non-password handlers
        raise ``TypeError`` — see :meth:`compute_encrypted_key`.
        """
        from .standard_security_handler import StandardSecurityHandler

        if not isinstance(self, StandardSecurityHandler):
            raise TypeError(
                f"{type(self).__name__} does not derive a /U entry from a"
                " password."
            )
        return StandardSecurityHandler.compute_user_password(
            password,
            o if o is not None else b"",
            permissions if permissions is not None else 0,
            document_id if document_id is not None else b"",
            revision if revision is not None else self._revision,
            (length_in_bits // 8)
            if length_in_bits is not None
            else (self._key_length // 8),
            encrypt_metadata if encrypt_metadata is not None else True,
        )

    def compute_owner_password(
        self,
        owner_password: bytes,
        user_password: bytes,
        revision: int | None = None,
        length_in_bits: int | None = None,
    ) -> bytes:
        """Compute the /O entry from owner+user passwords.

        Routes to the standard handler's algorithm 3. Non-password handlers
        raise ``TypeError`` — see :meth:`compute_encrypted_key`.
        """
        from .standard_security_handler import StandardSecurityHandler

        if not isinstance(self, StandardSecurityHandler):
            raise TypeError(
                f"{type(self).__name__} does not derive a /O entry from"
                " owner/user passwords."
            )
        return StandardSecurityHandler.compute_owner_password(
            owner_password,
            user_password,
            revision if revision is not None else self._revision,
            (length_in_bits // 8)
            if length_in_bits is not None
            else (self._key_length // 8),
        )

    # --------------------------------------------------- COSBase dispatch

    def decrypt(self, obj: object, obj_num: int, gen_num: int) -> object:
        """Mirror ``SecurityHandler#decrypt`` (line 476).

        Dispatches a COSBase to the appropriate string / stream / dict /
        array decryption helper. Non-COS objects (or anything not in the
        dispatch table) are returned unchanged.
        """
        # Lazy imports — these submodules import COS types which live below
        # the encryption package in the dependency order.
        from pypdfbox.cos.cos_array import COSArray  # noqa: PLC0415
        from pypdfbox.cos.cos_dictionary import COSDictionary  # noqa: PLC0415
        from pypdfbox.cos.cos_stream import COSStream  # noqa: PLC0415
        from pypdfbox.cos.cos_string import COSString  # noqa: PLC0415

        if isinstance(obj, COSString):
            return self._decrypt_string_if_absent(obj, obj_num, gen_num)
        if isinstance(obj, COSStream):
            return self._decrypt_stream_if_absent(obj, obj_num, gen_num)
        if isinstance(obj, COSDictionary):
            return self._decrypt_dictionary(obj, obj_num, gen_num)
        if isinstance(obj, COSArray):
            return self._decrypt_array(obj, obj_num, gen_num)
        return obj

    def _objects_seen(self) -> set[int]:
        # IdentityHashMap-equivalent — we use id(obj) so distinct-but-equal
        # COSStrings stay differentiated (PDFBOX-4477).
        seen = getattr(self, "_decrypted_ids", None)
        if seen is None:
            seen = set()
            self._decrypted_ids = seen
        return seen

    def _decrypt_string_if_absent(
        self, string: object, obj_num: int, gen_num: int
    ) -> object:
        """Mirror ``SecurityHandler#decryptStringIfAbsent`` (line 454)."""
        seen = self._objects_seen()
        if id(string) in seen:
            return string
        # Identity filter short-circuit.
        if self._string_filter_name is not None and _is_identity(self._string_filter_name):
            seen.add(id(string))
            return string
        get_bytes = getattr(string, "get_bytes", None)
        set_value = getattr(string, "set_value", None)
        if not callable(get_bytes) or not callable(set_value):
            return string
        # Route through ``decrypt_string`` (not the raw ``_decrypt``) so the
        # V4/V5 ``StandardSecurityHandler`` override honours the /StrF crypt
        # filter — e.g. a /StrF /Identity slot leaves strings cleartext while
        # streams stay AES-enciphered (PDF 32000-1 §7.6.5). The base handler's
        # ``decrypt_string`` delegates straight to ``_decrypt``, so V<4
        # behaviour is unchanged.
        plain = self.decrypt_string(get_bytes(), obj_num, gen_num)
        set_value(plain)
        seen.add(id(string))
        return string

    def _decrypt_stream_if_absent(
        self, stream: object, obj_num: int, gen_num: int
    ) -> object:
        """Mirror ``SecurityHandler#decryptStreamIfAbsent`` (line 507)."""
        seen = self._objects_seen()
        if id(stream) in seen:
            return stream
        seen.add(id(stream))
        self.decrypt_stream_in_place(stream, obj_num, gen_num)
        return stream

    def decrypt_stream_in_place(
        self, stream: object, obj_num: int, gen_num: int
    ) -> None:
        """Decrypt a COSStream in place. Mirrors upstream ``decryptStream``."""
        if self._stream_filter_name is not None and _is_identity(self._stream_filter_name):
            return
        # Skip cross-reference streams + (optional) Metadata.
        name: object = None
        try:
            from pypdfbox.cos.cos_name import COSName  # noqa: PLC0415
        except ImportError:
            COSName = None  # type: ignore[assignment]
        if COSName is not None:
            stream_type = None
            get_item = getattr(stream, "get_item", None)
            get_cos_name = getattr(stream, "get_cos_name", None)
            try:
                if callable(get_cos_name):
                    stream_type = get_cos_name(COSName.TYPE)
                elif callable(get_item):
                    stream_type = get_item("Type")
            except Exception:  # noqa: BLE001 — defensive, parity with upstream's broad catch
                stream_type = None
            if stream_type is not None:
                name = getattr(stream_type, "get_name", lambda: None)()
                if name == "XRef":
                    return
                if not self._decrypt_metadata and name == "Metadata":
                    return
        # Decrypt body bytes via the registered cos_stream encrypt path.
        get_raw = getattr(stream, "get_raw_bytes", None) or getattr(
            stream, "get_unfiltered_stream", None
        )
        set_raw = getattr(stream, "set_raw_bytes", None) or getattr(
            stream, "set_unfiltered_stream", None
        )
        if callable(get_raw) and callable(set_raw):
            try:
                raw = get_raw()
                if isinstance(raw, (bytes, bytearray, memoryview)):
                    # PDFBOX-3173 / PDFBOX-2603: a /Type /Metadata stream
                    # whose raw bytes already begin with the cleartext XMP
                    # marker ``<?xpacket`` is NOT actually encrypted — some
                    # producers emit cleartext metadata while still declaring
                    # /EncryptMetadata true. Upstream ``decryptStream`` warns
                    # and returns the bytes untouched in that case; mirror it
                    # so we don't corrupt the metadata by "decrypting"
                    # plaintext. The authoritative lazy read path applies the
                    # same guard in ``COSStream.set_security_handler`` (the
                    # primary decrypt point); this mirror covers the
                    # dict-walk entry too. Only fires when metadata decrypt is
                    # in effect (the ``not _decrypt_metadata`` early-return
                    # above already skips Metadata when the flag is off).
                    if (
                        self._decrypt_metadata
                        and name == "Metadata"
                        and bytes(raw)[:9] == b"<?xpacket"
                    ):
                        _LOG.warning(
                            "Metadata is not encrypted, but was expected to "
                            "be; read PDF specification about EncryptMetadata "
                            "(default value: true)"
                        )
                        return
                    # Route through ``decrypt_stream`` so the V4/V5 override
                    # honours the /StmF crypt filter (Identity ⇒ cleartext);
                    # base handler delegates to ``_decrypt`` for V<4 parity.
                    plain = self.decrypt_stream(bytes(raw), obj_num, gen_num)
                    set_raw(plain)
            except Exception:  # noqa: BLE001 — mirror upstream tolerant decrypt
                return

    def _decrypt_dictionary(
        self, dictionary: object, obj_num: int, gen_num: int
    ) -> object:
        """Mirror ``SecurityHandler#decryptDictionary`` (line 623)."""
        # /CF dictionaries should be left alone (PDFBOX-2936).
        get_item = getattr(dictionary, "get_item", None)
        if callable(get_item):
            try:
                cf = get_item("CF")
            except Exception:  # noqa: BLE001
                cf = None
            if cf is not None:
                return dictionary
        # Detect signature dicts so we don't re-encrypt /Contents.
        is_signature = False
        try:
            from pypdfbox.cos.cos_array import COSArray  # noqa: PLC0415
            from pypdfbox.cos.cos_string import COSString  # noqa: PLC0415

            type_val = (
                get_item("Type") if callable(get_item) else None
            )
            type_name = getattr(type_val, "get_name", lambda: None)() if type_val else None
            if type_name in ("Sig", "DocTimeStamp"):
                is_signature = True
            elif callable(get_item):
                contents = get_item("Contents")
                byterange = get_item("ByteRange")
                if isinstance(contents, COSString) and isinstance(byterange, COSArray):
                    is_signature = True
        except Exception:  # noqa: BLE001
            is_signature = False

        # ``entry_set()`` mirrors Java's ``Map.entrySet`` (line 636 upstream).
        entries = (
            getattr(dictionary, "entry_set", None)
            or getattr(dictionary, "items", None)
        )
        if callable(entries):
            for key, value in list(entries()):
                getter = getattr(key, "get_name", None)
                key_name = getter() if callable(getter) else key
                if is_signature and key_name == "Contents":
                    continue
                new_value = self.decrypt(value, obj_num, gen_num)
                if new_value is not value:
                    set_item = getattr(dictionary, "set_item", None)
                    if callable(set_item):  # pragma: no branch
                        # Defensive: dictionary is always a COSDictionary
                        # in the live decrypt pipeline (set_item is part
                        # of the COSDictionary contract).
                        set_item(key, new_value)
        return dictionary

    def _decrypt_array(
        self, array: object, obj_num: int, gen_num: int
    ) -> object:
        """Mirror ``SecurityHandler#decryptArray`` (line 727)."""
        size = len(array)  # type: ignore[arg-type]
        setter = getattr(array, "set", None)
        for i in range(size):
            elem = array[i]  # type: ignore[index]
            replaced = self.decrypt(elem, obj_num, gen_num)
            if replaced is not elem:
                if callable(setter):
                    setter(i, replaced)
                else:
                    array[i] = replaced  # type: ignore[index]
        return array

    # Public-name parity wrappers for upstream's private helpers. They keep
    # subclasses + tests one method-name lookup away from the upstream Java
    # references in the parity report.
    def decrypt_dictionary(
        self, dictionary: object, obj_num: int, gen_num: int
    ) -> object:
        """Public alias for :meth:`_decrypt_dictionary`."""
        return self._decrypt_dictionary(dictionary, obj_num, gen_num)

    def decrypt_array(
        self, array: object, obj_num: int, gen_num: int
    ) -> object:
        """Public alias for :meth:`_decrypt_array`."""
        return self._decrypt_array(array, obj_num, gen_num)

    def decrypt_stream_if_absent(
        self, stream: object, obj_num: int, gen_num: int
    ) -> object:
        """Public alias for :meth:`_decrypt_stream_if_absent`."""
        return self._decrypt_stream_if_absent(stream, obj_num, gen_num)

    def decrypt_string_if_absent(
        self, string: object, obj_num: int, gen_num: int
    ) -> object:
        """Public alias for :meth:`_decrypt_string_if_absent`."""
        return self._decrypt_string_if_absent(string, obj_num, gen_num)

    # ------------------------------------------------------------ AES helpers

    def prepare_aes_initialization_vector(
        self,
        decrypt: bool,
        iv: bytearray,
        data: object,
        output: object | None,
    ) -> bool:
        """Mirror ``SecurityHandler#prepareAESInitializationVector`` (line 404).

        On decrypt, reads a 16-byte IV from ``data`` into ``iv`` and returns
        ``True``; returns ``False`` if the stream is empty (parity with
        PDFBox's silent skip on zero-length payloads). On encrypt,
        generates a random IV via :meth:`get_secure_random`, copies it into
        ``iv``, and writes it to ``output``.
        """
        if decrypt:
            read = getattr(data, "read", None)
            if not callable(read):
                raise TypeError("data must be a readable stream on decrypt")
            chunk = bytes(read(16))
            if len(chunk) == 0:
                return False
            if len(chunk) != 16:
                raise OSError(
                    "AES initialization vector not fully read: only "
                    f"{len(chunk)} bytes read instead of 16"
                )
            iv[: len(chunk)] = chunk
            return True
        rng = self.get_secure_random()
        randbytes = getattr(rng, "randbytes", None) or getattr(rng, "read", None)
        if callable(randbytes):
            generated = bytes(randbytes(16))
        elif callable(rng):
            generated = bytes(rng(16))
        else:
            generated = _os.urandom(16)
        iv[: len(generated)] = generated
        if output is not None:
            write = getattr(output, "write", None)
            if callable(write):  # pragma: no branch
                # Defensive: output is always a writable stream when
                # supplied; the False arm has no live caller.
                write(bytes(iv))
        return True

    def create_cipher(self, key: bytes, iv: bytes, decrypt: bool) -> Cipher:
        """Mirror ``SecurityHandler#createCipher`` (line 393).

        Builds an ``AES/CBC/PKCS5Padding`` :class:`cryptography.Cipher`. The
        caller is responsible for adding / stripping PKCS#7 padding (this
        helper is a thin wrapper, like the upstream JCE call site).
        """
        return Cipher(algorithms.AES(bytes(key)), modes.CBC(bytes(iv)))

    def encrypt_data_rc4(
        self,
        final_key: bytes,
        input_data: bytes | object,
        output: object | None = None,
    ) -> bytes:
        """Mirror ``SecurityHandler#encryptDataRC4`` (line 285 / 301).

        Both upstream overloads (``InputStream``, ``byte[]``) collapse to
        this single bytes-aware helper. Returns the encrypted bytes; if
        ``output`` is provided the bytes are also written to it.
        """
        if isinstance(input_data, (bytes, bytearray, memoryview)):
            data = bytes(input_data)
        else:
            read = getattr(input_data, "read", None)
            if not callable(read):
                raise TypeError(
                    "input_data must be bytes-like or expose .read()"
                )
            data = bytes(read())
        result = _rc4(bytes(final_key), data)
        if output is not None:
            write = getattr(output, "write", None)
            if callable(write):
                write(result)
        return result

    def encrypt_data_ae_sother(
        self,
        final_key: bytes,
        data: bytes | object,
        output: object | None = None,
        decrypt: bool = False,
    ) -> bytes:
        """Encrypt or decrypt ``data`` with AES-128 / per-object key.

        Mirror of upstream private
        ``SecurityHandler.encryptDataAESother(byte[] finalKey,
        InputStream data, OutputStream output, boolean decrypt)``
        (line 318 of ``SecurityHandler.java``). The "other" suffix in
        the upstream name distinguishes the per-object AES variant
        from the AES-256 file-key variant in
        :meth:`encrypt_data_aes256`.

        Snake-cased letter-by-letter from the PDFBox name
        (``encryptDataAESother`` → ``encrypt_data_ae_sother``).
        Returns the produced bytes; writes them to ``output`` if
        provided.
        """
        if isinstance(data, (bytes, bytearray, memoryview)):
            payload = bytes(data)
        else:
            read = getattr(data, "read", None)
            if not callable(read):
                raise TypeError("data must be bytes-like or expose .read()")
            payload = bytes(read())
        if decrypt:
            result = _aes_cbc_decrypt(final_key, payload)
        else:
            result = _aes_cbc_encrypt(final_key, payload)
        if output is not None:
            write = getattr(output, "write", None)
            if callable(write):
                write(result)
        return result

    def encrypt_data_aes256(
        self,
        data: bytes | object,
        output: object | None = None,
        decrypt: bool = False,
    ) -> bytes:
        """Mirror ``SecurityHandler#encryptDataAES256`` (line 358).

        AES-256 with the file-encryption key directly (no per-object salt).
        Returns the produced bytes; writes them to ``output`` if provided.
        """
        if self._encryption_key is None:
            raise ValueError("encryption_key not set")
        if isinstance(data, (bytes, bytearray, memoryview)):
            payload = bytes(data)
        else:
            read = getattr(data, "read", None)
            if not callable(read):
                raise TypeError("data must be bytes-like or expose .read()")
            payload = bytes(read())
        if decrypt:
            result = _aes_cbc_decrypt(self._encryption_key, payload)
        else:
            result = _aes_cbc_encrypt(self._encryption_key, payload)
        if output is not None:
            write = getattr(output, "write", None)
            if callable(write):
                write(result)
        return result

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
    iv = _os.urandom(16)
    padder = _padding.PKCS7(128).padder()
    padded = padder.update(data) + padder.finalize()
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    enc = cipher.encryptor()
    return iv + enc.update(padded) + enc.finalize()


# Default secure-random source: a tiny shim with a ``read(n)`` method so
# callers can swap in any compatible RNG via ``set_custom_secure_random``.
class _DefaultSecureRandom:
    """Stand-in for ``java.security.SecureRandom`` backed by ``os.urandom``."""

    def read(self, n: int) -> bytes:
        return _os.urandom(int(n))

    # ``random.Random``-compatible alias for callers that prefer it.
    def randbytes(self, n: int) -> bytes:
        return _os.urandom(int(n))

    def __call__(self, n: int) -> bytes:
        return _os.urandom(int(n))


_DEFAULT_SECURE_RANDOM = _DefaultSecureRandom()


def _is_identity(name: object) -> bool:
    """Return ``True`` if ``name`` refers to the /Identity crypt filter."""
    if name is None:
        return False
    candidates: list[object] = []
    get_name = getattr(name, "get_name", None)
    if callable(get_name):
        with contextlib.suppress(Exception):
            candidates.append(get_name())
    candidates.append(name)
    return any(isinstance(c, str) and c == "Identity" for c in candidates)


# Silence unused-import warning when ``io`` isn't used at module level.
_ = _io


__all__ = ["SecurityHandler"]
