"""RC4 stream cipher used by the legacy Standard security handler.

Mirrors ``org.apache.pdfbox.pdmodel.encryption.RC4Cipher`` (PDFBox 3.x;
Java path ``pdfbox/src/main/java/org/apache/pdfbox/pdmodel/encryption/RC4Cipher.java``).

Library-first remains the preferred approach for AES, but the
``cryptography`` package's ARC4 binding rejects key sizes other than 5,
7, 8, 16, 24, 32 bytes — PDF's /V 1 / /V 2 encryption allows 1..32. To
preserve upstream's exact 1..32 tolerance we implement the KSA + PRGA
loop directly here; it matches the Java source byte-for-byte and is
small / audited / has no algorithmic novelty.
"""

from __future__ import annotations

from typing import BinaryIO


class RC4Cipher:
    """An implementation of the RC4 stream cipher (PDFBox parity).

    The upstream constructor takes no arguments; the key is supplied via
    :meth:`set_key`. The salt-array + b/c indices track the running PRGA
    state exactly as upstream does.
    """

    def __init__(self) -> None:
        self.salt: list[int] = [0] * 256
        self.b: int = 0
        self.c: int = 0

    def set_key(self, key: bytes | bytearray | memoryview) -> None:
        """Reset the key. Mirrors ``RC4Cipher.setKey`` (Java line 47).

        Per upstream, ``key`` must be 1..32 bytes long.
        """
        key_bytes = bytes(key)
        if not 1 <= len(key_bytes) <= 32:
            raise ValueError("number of bytes must be between 1 and 32")
        self.b = 0
        self.c = 0
        for i in range(256):
            self.salt[i] = i
        key_index = 0
        salt_index = 0
        for i in range(256):
            salt_index = (self._fix_byte(key_bytes[key_index]) + self.salt[i] + salt_index) % 256
            self._swap(i, salt_index)
            key_index = (key_index + 1) % len(key_bytes)

    @staticmethod
    def fix_byte(value: int) -> int:
        """Mirror of upstream's ``fixByte`` — kept for parity.

        Python ``bytes`` indexing already returns ``0..255``; this helper
        exists upstream because Java's ``byte`` is signed.
        """
        return value

    # Underscore-prefixed alias for in-module callers.
    _fix_byte = fix_byte

    def swap(self, first_index: int, second_index: int) -> None:
        """Mirror of upstream's ``swap`` — swap two salt entries in place."""
        tmp = self.salt[first_index]
        self.salt[first_index] = self.salt[second_index]
        self.salt[second_index] = tmp

    _swap = swap

    def encrypt(self, a_byte: int) -> int:
        """Mirror of upstream's ``encrypt`` — PRGA step on a single byte."""
        self.b = (self.b + 1) % 256
        self.c = (self.salt[self.b] + self.c) % 256
        self.swap(self.b, self.c)
        salt_index = (self.salt[self.b] + self.salt[self.c]) % 256
        return (a_byte ^ self.salt[salt_index]) & 0xFF

    _encrypt = encrypt

    def write(
        self,
        data: bytes | bytearray | BinaryIO,
        output: BinaryIO,
    ) -> None:
        """Encrypt ``data`` and write to ``output``.

        Mirrors the two upstream ``write(byte[], OutputStream)`` and
        ``write(InputStream, OutputStream)`` overloads (Java lines 131
        and 144); collapsed into a single Python method.
        """
        if isinstance(data, (bytes, bytearray, memoryview)):
            output.write(bytes(self.encrypt(b) for b in bytes(data)))
            return
        # Treat as an input stream (mirrors PDFBox's 1024-byte buffer).
        while True:
            chunk = data.read(1024)
            if not chunk:
                break
            output.write(bytes(self.encrypt(b) for b in chunk))


__all__ = ["RC4Cipher"]
