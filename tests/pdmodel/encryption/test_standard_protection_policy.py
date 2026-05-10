"""Hand-written coverage for :class:`StandardProtectionPolicy`.

The constructor / accessor surface is already exercised through
``test_pd_encryption.py`` — this module focuses on the predicate helpers
(``is_owner_password_set`` / ``is_user_password_set`` /
``is_password_protected``) and the :py:meth:`clear_passwords` convenience.

These have no direct upstream equivalent (Java defaults the password
fields to the empty string and relies on GC for cleanup), so they exist
to keep call sites idiomatic when porting consumer code.
"""

from __future__ import annotations

from pypdfbox.pdmodel.encryption import (
    AccessPermission,
    StandardProtectionPolicy,
)

# ---------- is_owner_password_set ----------


def test_is_owner_password_set_false_when_unset() -> None:
    policy = StandardProtectionPolicy()
    assert policy.is_owner_password_set() is False


def test_is_owner_password_set_false_for_empty_string() -> None:
    """Empty string matches upstream's Java default and produces no actual
    encryption protection — treat it the same as ``None``."""
    policy = StandardProtectionPolicy(owner_password="")
    assert policy.is_owner_password_set() is False


def test_is_owner_password_set_true_after_constructor() -> None:
    policy = StandardProtectionPolicy(owner_password="own3r")
    assert policy.is_owner_password_set() is True


def test_is_owner_password_set_true_after_setter() -> None:
    policy = StandardProtectionPolicy()
    policy.set_owner_password("own3r")
    assert policy.is_owner_password_set() is True


def test_is_owner_password_set_flips_back_to_false_when_cleared() -> None:
    policy = StandardProtectionPolicy(owner_password="own3r")
    policy.set_owner_password(None)
    assert policy.is_owner_password_set() is False


# ---------- is_user_password_set ----------


def test_is_user_password_set_false_when_unset() -> None:
    policy = StandardProtectionPolicy()
    assert policy.is_user_password_set() is False


def test_is_user_password_set_false_for_empty_string() -> None:
    policy = StandardProtectionPolicy(user_password="")
    assert policy.is_user_password_set() is False


def test_is_user_password_set_true_after_constructor() -> None:
    policy = StandardProtectionPolicy(user_password="us3r")
    assert policy.is_user_password_set() is True


def test_is_user_password_set_true_after_setter() -> None:
    policy = StandardProtectionPolicy()
    policy.set_user_password("us3r")
    assert policy.is_user_password_set() is True


def test_is_user_password_set_flips_back_to_false_when_cleared() -> None:
    policy = StandardProtectionPolicy(user_password="us3r")
    policy.set_user_password(None)
    assert policy.is_user_password_set() is False


# ---------- is_password_protected ----------


def test_is_password_protected_false_when_neither_set() -> None:
    policy = StandardProtectionPolicy()
    assert policy.is_password_protected() is False


def test_is_password_protected_false_for_empty_strings() -> None:
    policy = StandardProtectionPolicy(owner_password="", user_password="")
    assert policy.is_password_protected() is False


def test_is_password_protected_true_when_only_owner_set() -> None:
    # Owner-only is the common "user opens with no password" pattern — the
    # predicate must report protection regardless of which slot is filled.
    policy = StandardProtectionPolicy(owner_password="own3r")
    assert policy.is_password_protected() is True


def test_is_password_protected_true_when_only_user_set() -> None:
    policy = StandardProtectionPolicy(user_password="us3r")
    assert policy.is_password_protected() is True


def test_is_password_protected_true_when_both_set() -> None:
    policy = StandardProtectionPolicy(
        owner_password="own3r", user_password="us3r"
    )
    assert policy.is_password_protected() is True


def test_is_password_protected_or_logic_matches_helpers() -> None:
    # Defensive — the predicate is documented as the OR of the two more
    # granular helpers; verify that contract holds across all four corners.
    for owner, user in (
        (None, None),
        ("o", None),
        (None, "u"),
        ("o", "u"),
    ):
        policy = StandardProtectionPolicy(
            owner_password=owner, user_password=user
        )
        expected = policy.is_owner_password_set() or policy.is_user_password_set()
        assert policy.is_password_protected() is expected


# ---------- clear_passwords ----------


def test_clear_passwords_resets_both_to_none() -> None:
    policy = StandardProtectionPolicy(
        owner_password="own3r", user_password="us3r"
    )
    policy.clear_passwords()
    assert policy.get_owner_password() is None
    assert policy.get_user_password() is None
    assert policy.is_password_protected() is False


def test_clear_passwords_is_idempotent() -> None:
    policy = StandardProtectionPolicy()
    policy.clear_passwords()
    policy.clear_passwords()
    assert policy.get_owner_password() is None
    assert policy.get_user_password() is None


def test_clear_passwords_preserves_permissions_object() -> None:
    """clear_passwords only touches the password slots — the permissions
    AccessPermission must keep its identity (callers may have already
    captured a reference to it for further mutation)."""
    perms = AccessPermission()
    perms.set_can_print(False)
    policy = StandardProtectionPolicy(
        owner_password="own3r",
        user_password="us3r",
        permissions=perms,
    )
    policy.clear_passwords()
    held = policy.get_permissions()
    assert held is perms
    assert held.can_print() is False


def test_clear_passwords_preserves_inherited_protection_policy_state() -> None:
    """clear_passwords must leave the inherited ProtectionPolicy state
    (key length / prefer-AES) untouched — only the password slots are
    in scope for the helper."""
    policy = StandardProtectionPolicy(
        owner_password="own3r", user_password="us3r"
    )
    policy.set_encryption_key_length(256)
    policy.set_prefer_aes(True)
    policy.clear_passwords()
    assert policy.get_encryption_key_length() == 256
    assert policy.is_prefer_aes() is True


# ---------- predicate independence from permissions ----------


def test_predicates_ignore_permissions_object() -> None:
    """Setting custom permissions must not influence the password predicates
    — they only inspect the password slots."""
    perms = AccessPermission(0)  # nothing allowed
    policy = StandardProtectionPolicy(permissions=perms)
    assert policy.is_owner_password_set() is False
    assert policy.is_user_password_set() is False
    assert policy.is_password_protected() is False
