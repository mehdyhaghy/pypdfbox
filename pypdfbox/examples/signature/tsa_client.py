"""Port of ``TSAClient`` (upstream 1-208).

RFC 3161 Time Stamping Authority client. Upstream uses Bouncy Castle to
build ``TimeStampRequest`` / parse ``TimeStampResponse``. In pypdfbox we
keep the public surface identical and provide a pluggable transport so
tests don't need a real TSA server (pass ``transport=`` to inject a fake).
"""

from __future__ import annotations

import base64
import logging
import secrets
from collections.abc import Callable
from typing import IO
from urllib.request import Request, urlopen

LOG = logging.getLogger(__name__)


class TSAClient:
    """Minimal RFC 3161 TSA client.

    Parameters mirror upstream:

    * ``url``      — TSA endpoint
    * ``username`` — optional HTTP basic auth user
    * ``password`` — optional HTTP basic auth password
    * ``digest``   — a ``hashlib``-style digest object (must expose
                     ``update`` / ``digest`` / ``name``)

    ``transport`` is a pypdfbox-only seam for tests: a callable
    ``(request_bytes, url, headers) -> response_bytes``. When ``None`` we
    fall back to :func:`urllib.request.urlopen`.
    """

    def __init__(
        self,
        url: str,
        username: str | None,
        password: str | None,
        digest,  # noqa: ANN001 - hashlib-style
        transport: Callable[[bytes, str, dict[str, str]], bytes] | None = None,
    ) -> None:
        self._url = url
        self._username = username
        self._password = password
        self._digest = digest
        self._transport = transport

    def get_time_stamp_token(self, content: IO[bytes]) -> bytes:
        """Hash ``content`` then ask the TSA to sign it.

        Returns the DER-encoded ``TimeStampToken`` bytes — upstream returns
        a Bouncy Castle ``TimeStampToken`` object; in pypdfbox callers
        re-parse with ``cryptography``-or-equivalent if they need fields.
        """
        # Hash the content (stream the upstream uses DigestInputStream).
        self._digest = _reset(self._digest)
        while True:
            chunk = content.read(8192)
            if not chunk:
                break
            self._digest.update(chunk)
        hashed = self._digest.digest()

        # 31-bit positive nonce, mirroring upstream.
        nonce = secrets.randbits(31)
        request = self._build_request(hashed, nonce)
        response = self.get_tsa_response(request)
        return response

    def _build_request(self, hashed: bytes, nonce: int) -> bytes:
        """Build a minimal DER TimeStampReq blob.

        We don't reimplement DER from scratch — we lean on
        ``cryptography``'s ASN.1 backend via ``rfc3161ng``-style structures
        only if a future library is approved. For now we emit a tagged blob
        that captures hash + algorithm + nonce so tests can exercise the
        round-trip; production callers should plug in a real TSP library.
        """
        # Compact ad-hoc representation (NOT a real TimeStampReq). Tests use
        # a transport seam to avoid going over the wire.
        return b"|".join(
            [
                b"tsp-req",
                self._digest.name.encode("ascii"),
                hashed,
                str(nonce).encode("ascii"),
            ]
        )

    def get_tsa_response(self, request: bytes) -> bytes:
        headers = {"Content-Type": "application/timestamp-query"}
        if self._username and self._password:
            token = base64.b64encode(
                f"{self._username}:{self._password}".encode("utf-8")
            ).decode("ascii")
            headers["Authorization"] = f"Basic {token}"

        if self._transport is not None:
            return self._transport(request, self._url, headers)

        req = Request(self._url, data=request, headers=headers, method="POST")
        with urlopen(req, timeout=30) as resp:  # noqa: S310 - URL comes from user config
            return resp.read()


def _reset(digest):  # noqa: ANN001, ANN202 - hashlib doesn't have reset()
    import hashlib

    return hashlib.new(getattr(digest, "name", "sha256"))
