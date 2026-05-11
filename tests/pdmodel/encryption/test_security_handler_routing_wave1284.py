"""Wave 1284 — verify the base SecurityHandler routes password derivation."""

from __future__ import annotations

import pytest

from pypdfbox.pdmodel.encryption.public_key_security_handler import (
    PublicKeySecurityHandler,
)
from pypdfbox.pdmodel.encryption.security_handler import SecurityHandler
from pypdfbox.pdmodel.encryption.standard_security_handler import (
    StandardSecurityHandler,
)


def test_standard_handler_compute_user_password_routes_through_base() -> None:
    # Going through the abstract base routes back to the concrete subclass
    # (revision 4 path through algorithm 4).
    handler = StandardSecurityHandler()
    handler._revision = 4  # noqa: SLF001
    handler._key_length = 128  # noqa: SLF001
    out = SecurityHandler.compute_user_password(
        handler,
        b"password",
        o=b"o" * 32,
        permissions=-4,
        document_id=b"d" * 16,
    )
    assert isinstance(out, bytes)
    assert len(out) == 32


def test_standard_handler_compute_owner_password_routes_through_base() -> None:
    handler = StandardSecurityHandler()
    handler._revision = 4  # noqa: SLF001
    handler._key_length = 128  # noqa: SLF001
    out = SecurityHandler.compute_owner_password(
        handler, b"owner", b"user",
    )
    assert isinstance(out, bytes)
    assert len(out) == 32


def test_public_key_handler_compute_user_password_raises_type_error() -> None:
    handler = PublicKeySecurityHandler()
    with pytest.raises(TypeError, match="does not derive a /U entry"):
        handler.compute_user_password(b"pw")


def test_public_key_handler_compute_owner_password_raises_type_error() -> None:
    handler = PublicKeySecurityHandler()
    with pytest.raises(TypeError, match="does not derive a /O entry"):
        handler.compute_owner_password(b"owner", b"user")


def test_public_key_handler_compute_encrypted_key_raises_type_error() -> None:
    handler = PublicKeySecurityHandler()
    with pytest.raises(TypeError, match="does not derive keys"):
        handler.compute_encrypted_key(b"pw")
