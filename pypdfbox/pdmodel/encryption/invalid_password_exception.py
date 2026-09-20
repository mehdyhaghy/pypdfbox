"""Indicates that an invalid password was supplied.

Mirrors ``org.apache.pdfbox.pdmodel.encryption.InvalidPasswordException``.
"""


class InvalidPasswordException(OSError):
    """Raised when neither owner nor user password validates."""

    def __init__(
        self,
        message: str = "Cannot decrypt PDF, the password is incorrect",
    ) -> None:
        super().__init__(message)
