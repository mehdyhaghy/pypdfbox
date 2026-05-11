"""Port of the nested ``SHA1DigestCalculator`` class from ``OcspHelper``.

Upstream this is ``OcspHelper.SHA1DigestCalculator`` (lines 616-651). It's a
``DigestCalculator`` adapter that feeds writes into a SHA-1 hasher and
returns the digest. We wrap ``hashlib`` (already a stdlib library
implementation) so we don't reimplement SHA-1.
"""

from __future__ import annotations

import hashlib
import io


class SHA1DigestCalculator:
    """Streaming SHA-1 digest calculator with a ``DigestCalculator``-like API.

    Upstream returns an ``AlgorithmIdentifier`` and exposes a writable
    output stream. The Python flavour exposes ``get_output_stream`` (a
    :class:`io.BytesIO`-like wrapper) and ``get_digest`` for the final hash.
    """

    #: OID for SHA-1 (1.3.14.3.2.26) — matches the upstream identifier.
    ALGORITHM_OID = "1.3.14.3.2.26"

    def __init__(self) -> None:
        self._hash = hashlib.sha1(usedforsecurity=False)
        self._stream = _DigestStream(self._hash)

    def get_algorithm_identifier(self) -> str:
        """Return the OID of the digest algorithm."""
        return self.ALGORITHM_OID

    def get_output_stream(self) -> _DigestStream:
        """Return a stream that updates the underlying SHA-1 state on write."""
        return self._stream

    def get_digest(self) -> bytes:
        return self._hash.digest()


class _DigestStream(io.RawIOBase):
    """Tiny ``write``-only adapter that forwards bytes into a hasher."""

    def __init__(self, hasher) -> None:  # noqa: ANN001
        super().__init__()
        self._hasher = hasher

    def writable(self) -> bool:  # pragma: no cover - trivial
        return True

    def write(self, b) -> int:  # type: ignore[override]  # noqa: ANN001
        self._hasher.update(b)
        return len(b)
