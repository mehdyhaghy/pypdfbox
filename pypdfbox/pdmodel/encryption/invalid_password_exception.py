"""Indicates that an invalid password was supplied.

Mirrors ``org.apache.pdfbox.pdmodel.encryption.InvalidPasswordException``.
"""

from __future__ import annotations


class InvalidPasswordException(OSError):
    """Raised when neither owner nor user password validates."""

    def __init__(
        self,
        message: str = "Cannot decrypt PDF, the password is incorrect",
    ) -> None:
        super().__init__(message)
