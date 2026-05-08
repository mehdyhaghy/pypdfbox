from __future__ import annotations

DEFAULT_KEY_LENGTH: int = 40
_VALID_KEY_LENGTHS: frozenset[int] = frozenset({40, 128, 256})


class ProtectionPolicy:
    """
    Abstract base mirroring PDFBox ``ProtectionPolicy`` — describes *how*
    a document should be encrypted; subclasses (``StandardProtectionPolicy``,
    public-key variants) carry the credential material.
    """

    # Mirrors the upstream ``private static final short DEFAULT_KEY_LENGTH``
    # constant. Exposed as a class attribute so subclasses / callers can
    # reference it without re-importing the module-level alias.
    DEFAULT_KEY_LENGTH: int = DEFAULT_KEY_LENGTH

    def __init__(self) -> None:
        self._encryption_key_length: int = DEFAULT_KEY_LENGTH
        self._prefer_aes: bool = False

    def get_encryption_key_length(self) -> int:
        return self._encryption_key_length

    def getEncryptionKeyLength(self) -> int:  # noqa: N802
        """Alias for PDFBox's Java-style ``getEncryptionKeyLength``."""
        return self.get_encryption_key_length()

    def set_encryption_key_length(self, bits: int) -> None:
        if not isinstance(bits, int) or isinstance(bits, bool):
            raise TypeError(
                f"encryption key length must be an int, got {type(bits).__name__}"
            )
        if bits not in _VALID_KEY_LENGTHS:
            raise ValueError(
                f"invalid key length {bits}; expected one of {sorted(_VALID_KEY_LENGTHS)}"
            )
        self._encryption_key_length = bits

    def setEncryptionKeyLength(self, bits: int) -> None:  # noqa: N802
        """Alias for PDFBox's Java-style ``setEncryptionKeyLength``."""
        self.set_encryption_key_length(bits)

    def is_prefer_aes(self) -> bool:
        return self._prefer_aes

    def isPreferAES(self) -> bool:  # noqa: N802
        """Alias for PDFBox's Java-style ``isPreferAES``."""
        return self.is_prefer_aes()

    def set_prefer_aes(self, b: bool) -> None:
        if not isinstance(b, bool):
            raise TypeError(f"prefer_aes must be a bool, got {type(b).__name__}")
        self._prefer_aes = b

    def setPreferAES(self, b: bool) -> None:  # noqa: N802
        """Alias for PDFBox's Java-style ``setPreferAES``."""
        self.set_prefer_aes(b)


__all__ = ["DEFAULT_KEY_LENGTH", "ProtectionPolicy"]
