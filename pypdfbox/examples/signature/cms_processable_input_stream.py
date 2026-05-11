"""Port of ``CMSProcessableInputStream`` (upstream 1-71).

Upstream this wraps a stream so the Bouncy Castle CMS signer can pull
content lazily. In pypdfbox we sign with the ``cryptography`` PKCS#7 API,
which accepts ``bytes``, so this class is a thin compatibility wrapper
that lets example code mirror the upstream shape.
"""

from __future__ import annotations

from typing import IO


class CMSProcessableInputStream:
    """Wrap an input stream as a CMS-processable content carrier."""

    #: OID for ``id-data`` (1.2.840.113549.1.7.1) — the CMS default content type.
    CONTENT_TYPE_DATA = "1.2.840.113549.1.7.1"

    def __init__(
        self,
        stream: IO[bytes],
        content_type: str | None = None,
    ) -> None:
        self._stream = stream
        self._content_type = content_type or self.CONTENT_TYPE_DATA

    def get_content(self) -> IO[bytes]:
        """Return the wrapped stream (upstream ``getContent``)."""
        return self._stream

    def write(self, out: IO[bytes]) -> None:
        """Copy the content stream to ``out`` and close the source."""
        try:
            while True:
                chunk = self._stream.read(8192)
                if not chunk:
                    break
                out.write(chunk)
        finally:
            self._stream.close()

    def get_content_type(self) -> str:
        return self._content_type
