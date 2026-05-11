"""Port of ``ValidationTimeStamp`` (upstream 1-142).

Wraps :class:`TSAClient` so callers can ask for a signed-timestamp token
or extend an existing CMS ``SignedData`` blob with one.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from io import BytesIO
from typing import IO

from pypdfbox.examples.signature.tsa_client import TSAClient


class ValidationTimeStamp:
    """Adds RFC 3161 timestamps to CMS signed data."""

    def __init__(
        self,
        tsa_url: str | None,
        transport: Callable[[bytes, str, dict[str, str]], bytes] | None = None,
    ) -> None:
        self._tsa_client: TSAClient | None = None
        if tsa_url:
            digest = hashlib.sha256()
            self._tsa_client = TSAClient(tsa_url, None, None, digest, transport=transport)

    def get_time_stamp_token(self, content: IO[bytes]) -> bytes:
        """Return DER-encoded TimeStampToken bytes for ``content``."""
        if self._tsa_client is None:
            raise ValueError("No TSA URL configured")
        return self._tsa_client.get_time_stamp_token(content)

    def sign_time_stamp(self, signer_information: bytes) -> bytes:
        """Augment one CMS SignerInfo with a TST (upstream private 116)."""
        return self.add_signed_time_stamp(signer_information)

    def add_signed_time_stamp(self, signed_data: bytes) -> bytes:
        """Augment a CMS ``SignedData`` blob with a TST unsigned attribute.

        Upstream this rewrites the BC ``SignerInformation`` and returns a
        new ``CMSSignedData``. In pypdfbox we keep the API shape; the
        returned bytes carry the concatenated token (callers replacing this
        with a proper TST-attribute injection can subclass).
        """
        if self._tsa_client is None:
            return signed_data
        token = self._tsa_client.get_time_stamp_token(BytesIO(signed_data))
        return signed_data + token
