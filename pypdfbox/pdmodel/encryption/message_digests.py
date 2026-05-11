"""Factory helpers for the message-digest algorithms used by PDF encryption.

Mirrors ``org.apache.pdfbox.pdmodel.encryption.MessageDigests`` (PDFBox 3.x;
Java path ``pdfbox/src/main/java/org/apache/pdfbox/pdmodel/encryption/MessageDigests.java``).
Library-first: delegates to ``cryptography.hazmat.primitives.hashes`` for the
underlying primitives instead of reimplementing MD5/SHA-1/SHA-256.
"""

from __future__ import annotations

from cryptography.hazmat.primitives import hashes


class MessageDigests:
    """Utility class for creating ``hashes.Hash`` instances.

    The Java upstream is a package-private final class with three static
    factory methods. The Python port keeps the same surface: methods are
    static and return a freshly initialised :class:`hashes.Hash` ready to
    receive ``update`` / ``finalize`` calls.
    """

    def __init__(self) -> None:
        # Java declares a private no-arg constructor; mirror that semantic
        # by making instances effectively useless (matches upstream
        # ``private MessageDigests()`` — the class is purely a static
        # namespace).
        raise TypeError("MessageDigests is a utility class — use the classmethods")

    @staticmethod
    def get_md5() -> hashes.Hash:
        """Return an MD5 digest instance.

        Mirrors ``MessageDigests.getMD5`` (Java line 35). Used by the
        Standard security handler for the legacy /V 1, /V 2, /V 4
        password-derivation rounds.
        """
        return hashes.Hash(hashes.MD5())

    @staticmethod
    def get_sha1() -> hashes.Hash:
        """Return a SHA-1 digest instance.

        Mirrors ``MessageDigests.getSHA1`` (Java line 51). Used by the
        public-key handler when computing recipient hashes.
        """
        return hashes.Hash(hashes.SHA1())

    @staticmethod
    def get_sha256() -> hashes.Hash:
        """Return a SHA-256 digest instance.

        Mirrors ``MessageDigests.getSHA256`` (Java line 67). Used by the
        Standard security handler for /V 5 (PDF 2.0) password derivation.
        """
        return hashes.Hash(hashes.SHA256())


__all__ = ["MessageDigests"]
