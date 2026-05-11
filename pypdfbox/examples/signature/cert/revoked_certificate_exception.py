"""Port of ``RevokedCertificateException`` (upstream lines 1-48)."""

from __future__ import annotations

import datetime as _dt


class RevokedCertificateException(Exception):
    """Exception raised when a certificate is found to be revoked."""

    def __init__(
        self,
        message: str,
        revocation_time: _dt.datetime | None = None,
    ) -> None:
        super().__init__(message)
        self._revocation_time = revocation_time

    def get_revocation_time(self) -> _dt.datetime | None:
        """Return the revocation timestamp, or ``None`` if not provided."""
        return self._revocation_time
