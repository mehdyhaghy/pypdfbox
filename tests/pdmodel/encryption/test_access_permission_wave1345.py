"""Wave 1345: residual coverage for ``AccessPermission``.

Targets the 1-based ``is_permission_bit_on`` / ``set_permission_bit``
mirrors of the upstream private helpers (used internally by
``get_permission_bytes_for_public_key`` after read-only has been
applied).
"""

from __future__ import annotations

from pypdfbox.pdmodel.encryption.access_permission import AccessPermission


def test_is_permission_bit_on_for_default_instance() -> None:
    """Default (all-permissions) instance has every defined bit set."""
    ap = AccessPermission()
    # Bits 3..12 are the spec-defined permission bits.
    for bit in range(3, 13):
        assert ap.is_permission_bit_on(bit) is True


def test_is_permission_bit_on_returns_false_for_cleared_bit() -> None:
    """An instance constructed from 0 reports every bit as off."""
    ap = AccessPermission(0)
    for bit in range(1, 32):
        assert ap.is_permission_bit_on(bit) is False


def test_set_permission_bit_turns_bit_on() -> None:
    """``set_permission_bit(bit, True)`` sets the bit and returns ``True``."""
    ap = AccessPermission(0)
    assert ap.set_permission_bit(3, True) is True
    assert ap.is_permission_bit_on(3) is True
    # Other bits stay cleared.
    assert ap.is_permission_bit_on(4) is False


def test_set_permission_bit_turns_bit_off() -> None:
    """``set_permission_bit(bit, False)`` clears the bit and returns ``False``."""
    ap = AccessPermission()  # all bits on
    assert ap.set_permission_bit(3, False) is False
    assert ap.is_permission_bit_on(3) is False
    # Sibling bits unaffected.
    assert ap.is_permission_bit_on(4) is True


def test_set_permission_bit_ignores_read_only() -> None:
    """Upstream parity: this private helper bypasses the read-only gate
    (used internally after the caller has already locked the instance)."""
    ap = AccessPermission(0)
    ap.set_read_only()
    # Despite the lock, set_permission_bit still mutates the bytes.
    assert ap.set_permission_bit(3, True) is True
    assert ap.is_permission_bit_on(3) is True


def test_set_permission_bit_idempotent_returns_current_state() -> None:
    """Repeated ``True`` calls keep the bit set; repeated ``False`` keep cleared."""
    ap = AccessPermission(0)
    assert ap.set_permission_bit(5, True) is True
    assert ap.set_permission_bit(5, True) is True
    assert ap.set_permission_bit(5, False) is False
    assert ap.set_permission_bit(5, False) is False


def test_is_permission_bit_on_uses_1_based_indexing() -> None:
    """Bit 1 (1-based) corresponds to ``1 << 0``."""
    ap = AccessPermission(1)  # only bit 1 set
    assert ap.is_permission_bit_on(1) is True
    assert ap.is_permission_bit_on(2) is False
    assert ap.is_permission_bit_on(3) is False
