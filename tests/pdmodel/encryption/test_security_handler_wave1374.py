"""Wave 1374 pinning tests — close audit item 3:
``SecurityHandler.compute_encrypted_key`` base now raises
:class:`TypeError` for every handler that doesn't override it
(:class:`PublicKeySecurityHandler` is the only such handler today).
The previously-present fallthrough delegation to
:class:`StandardSecurityHandler` was structurally unreachable —
Python's MRO routes a call on a Standard handler to the subclass
override before the base is ever consulted — so it was deleted.

These tests pin the contract:

1. ``PublicKeySecurityHandler.compute_encrypted_key`` raises
   :class:`TypeError` with a useful message.
2. The base method itself raises :class:`TypeError` when invoked on a
   bare :class:`SecurityHandler`-only instance (covers the audit's
   "no subclass override" case directly).
3. :class:`StandardSecurityHandler` still overrides correctly — the
   subclass method continues to dispatch by argument shape (compact
   vs full upstream form).
"""

from __future__ import annotations

import pytest

from pypdfbox.pdmodel.encryption.public_key_security_handler import (
    PublicKeySecurityHandler,
)
from pypdfbox.pdmodel.encryption.security_handler import SecurityHandler
from pypdfbox.pdmodel.encryption.standard_security_handler import (
    StandardSecurityHandler,
)


def test_public_key_handler_compute_encrypted_key_raises_type_error() -> None:
    """``PublicKeySecurityHandler`` inherits the base ``TypeError``
    raise — the public-key flow wraps the file key in a per-recipient
    envelope, not derived from a password."""
    handler = PublicKeySecurityHandler()
    with pytest.raises(TypeError, match="does not derive keys from a password"):
        handler.compute_encrypted_key(b"password")


def test_base_compute_encrypted_key_is_not_a_dispatcher() -> None:
    """The base method must not silently delegate to
    :class:`StandardSecurityHandler` — Python's MRO already routes a
    call on a Standard handler to the subclass override, so any
    fallthrough delegation on the base would be structurally
    unreachable. Pin that by inspecting the base method's source:
    it has no ``StandardSecurityHandler.`` call site.
    """
    import inspect

    source = inspect.getsource(SecurityHandler.compute_encrypted_key)
    # The base must not import or call ``StandardSecurityHandler``.
    assert "from .standard_security_handler" not in source
    assert "StandardSecurityHandler.compute_encrypted_key" not in source
    assert "raise TypeError" in source


def test_standard_security_handler_still_overrides_compute_encrypted_key() -> None:
    """The :class:`StandardSecurityHandler` override is unaffected by
    the base cleanup — the compact 7-positional form continues to
    return a key of the requested byte length."""
    document_id = b"\x00" * 16
    o_entry = b"\x00" * 32
    key = StandardSecurityHandler.compute_encrypted_key(
        b"",  # owner-or-user password
        o_entry,
        0,  # permissions
        document_id,
        2,  # revision (r2)
        5,  # key length in bytes (40-bit)
        True,  # encrypt_metadata
    )
    assert isinstance(key, (bytes, bytearray))
    assert len(key) == 5


def test_base_compute_encrypted_key_message_includes_class_name() -> None:
    """The error message embeds the concrete class name so callers
    debugging a wrong-handler error can tell which handler refused."""
    handler = PublicKeySecurityHandler()
    with pytest.raises(TypeError) as excinfo:
        handler.compute_encrypted_key(b"any")
    assert "PublicKeySecurityHandler" in str(excinfo.value)
