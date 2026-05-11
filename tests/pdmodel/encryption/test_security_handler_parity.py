"""Upstream-name parity coverage for ``SecurityHandler`` accessors.

Mirrors the subset of ``org.apache.pdfbox.pdmodel.encryption.SecurityHandler``
public API that callers reach for directly (encryption_key, key_length, aes,
current_access_permission, decryption_material, decrypt_metadata flag, plus
the data convenience wrappers and the subclass-override placeholders).
"""

from __future__ import annotations

import io

import pytest

from pypdfbox.pdmodel.encryption.access_permission import AccessPermission
from pypdfbox.pdmodel.encryption.security_handler import SecurityHandler


class _BareHandler(SecurityHandler):
    """Concrete instantiable handler exposing the abstract base for tests."""

    def prepare_for_decryption(
        self,
        encryption: object,
        document_id: bytes,
        decryption_material: object,
    ) -> None:  # pragma: no cover — not exercised here
        pass

    def prepare_document(self, document: object) -> None:  # pragma: no cover
        pass


def _handler() -> _BareHandler:
    return _BareHandler()


# --------------------------------------------------------------- state round-trips


def test_encryption_key_round_trip() -> None:
    h = _handler()
    assert h.get_encryption_key() is None
    h.set_encryption_key(b"\x00\x11\x22\x33\x44")
    assert h.get_encryption_key() == b"\x00\x11\x22\x33\x44"


def test_key_length_round_trip() -> None:
    h = _handler()
    assert h.get_key_length() == 40
    h.set_key_length(128)
    assert h.get_key_length() == 128


def test_aes_round_trip() -> None:
    h = _handler()
    assert h.is_aes() is False
    h.set_aes(True)
    assert h.is_aes() is True
    h.set_aes(False)
    assert h.is_aes() is False


def test_revision_and_version_round_trip() -> None:
    h = _handler()
    h.set_revision(4)
    h.set_version(4)
    assert h.get_revision() == 4
    assert h.get_version() == 4


# --------------------------------------------------------- access permission


def test_current_access_permission_default_none() -> None:
    assert _handler().get_current_access_permission() is None


def test_current_access_permission_round_trip() -> None:
    h = _handler()
    perm = AccessPermission()
    h.set_current_access_permission(perm)
    assert h.get_current_access_permission() is perm


# --------------------------------------------------------- decryption material


def test_decryption_material_default_none() -> None:
    assert _handler().get_decryption_material() is None


def test_decryption_material_round_trip() -> None:
    h = _handler()
    sentinel = object()
    h.set_decryption_material(sentinel)
    assert h.get_decryption_material() is sentinel


# --------------------------------------------------------- metadata flag


def test_decrypt_metadata_default_true() -> None:
    assert _handler().is_decrypt_metadata() is True


def test_decrypt_metadata_round_trip() -> None:
    h = _handler()
    h.set_decrypt_metadata(False)
    assert h.is_decrypt_metadata() is False
    h.set_decrypt_metadata(True)
    assert h.is_decrypt_metadata() is True


# --------------------------------------------------------- data convenience


def test_decrypt_data_round_trip_rc4_bytes() -> None:
    h = _handler()
    h.set_encryption_key(b"K" * 5)
    h.set_revision(2)
    h.set_aes(False)
    ct = h.encrypt_data(b"hello", 1, 0)
    pt = h.decrypt_data(ct, 1, 0)
    assert pt == b"hello"


def test_decrypt_data_accepts_file_like() -> None:
    h = _handler()
    h.set_encryption_key(b"K" * 5)
    h.set_revision(2)
    ct = h.encrypt_data(b"hi there", 7, 0)
    pt = h.decrypt_data(io.BytesIO(ct), 7, 0)
    assert pt == b"hi there"


def test_encrypt_data_rejects_unsupported_input() -> None:
    h = _handler()
    h.set_encryption_key(b"K" * 5)
    h.set_revision(2)
    with pytest.raises(TypeError):
        h.encrypt_data(12345, 1, 0)  # type: ignore[arg-type]


# --------------------------------------------------------- placeholder subclass API


def test_compute_encrypted_key_rejected_on_non_password_handler() -> None:
    # Wave 1284: the base class now routes password derivation to the
    # standard handler; non-password handlers raise ``TypeError`` instead.
    with pytest.raises(TypeError, match="does not derive keys"):
        _handler().compute_encrypted_key(b"pw")


def test_compute_user_password_rejected_on_non_password_handler() -> None:
    with pytest.raises(TypeError, match="does not derive a /U entry"):
        _handler().compute_user_password(b"pw")


def test_compute_owner_password_rejected_on_non_password_handler() -> None:
    with pytest.raises(TypeError, match="does not derive a /O entry"):
        _handler().compute_owner_password(b"owner", b"user")
