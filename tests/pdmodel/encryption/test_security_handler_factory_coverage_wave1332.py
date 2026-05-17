"""Coverage-boost tests for ``SecurityHandlerFactory`` (wave 1332).

Targets:

* the :meth:`new_security_handler` dispatcher — both the
  ``ProtectionPolicy`` branch and the string-filter fallback;
* the ``None``-return branch of
  :meth:`new_security_handler_for_policy` when the policy type has no
  registered handler.
"""

from __future__ import annotations

from pypdfbox.pdmodel.encryption.public_key_protection_policy import (
    PublicKeyProtectionPolicy,
)
from pypdfbox.pdmodel.encryption.public_key_security_handler import (
    PublicKeySecurityHandler,
)
from pypdfbox.pdmodel.encryption.security_handler_factory import (
    SecurityHandlerFactory,
)
from pypdfbox.pdmodel.encryption.standard_protection_policy import (
    StandardProtectionPolicy,
)
from pypdfbox.pdmodel.encryption.standard_security_handler import (
    StandardSecurityHandler,
)


def test_new_security_handler_dispatches_policy_to_for_policy_path() -> None:
    factory = SecurityHandlerFactory.INSTANCE
    policy = StandardProtectionPolicy(owner_password="o", user_password="u")

    handler = factory.new_security_handler(policy)

    assert isinstance(handler, StandardSecurityHandler)


def test_new_security_handler_dispatches_public_key_policy_to_for_policy_path() -> None:
    factory = SecurityHandlerFactory.INSTANCE
    policy = PublicKeyProtectionPolicy()

    handler = factory.new_security_handler(policy)

    assert isinstance(handler, PublicKeySecurityHandler)


def test_new_security_handler_dispatches_string_to_for_filter_path() -> None:
    factory = SecurityHandlerFactory.INSTANCE

    handler = factory.new_security_handler(StandardSecurityHandler.FILTER)

    assert isinstance(handler, StandardSecurityHandler)


def test_new_security_handler_returns_none_for_unknown_filter_name() -> None:
    factory = SecurityHandlerFactory.INSTANCE

    assert factory.new_security_handler("DefinitelyNotAFilter") is None


def test_new_security_handler_for_policy_returns_none_for_unregistered_policy_type() -> None:
    factory = SecurityHandlerFactory.INSTANCE

    class _UnregisteredPolicy:
        """Stand-in policy type the factory has never been told about."""

    # Cast through ``object`` so mypy doesn't complain — the dispatcher
    # only cares about the runtime type when looking up the handler.
    assert factory.new_security_handler_for_policy(_UnregisteredPolicy()) is None  # type: ignore[arg-type]


def test_register_handler_rejects_duplicate_filter_name() -> None:
    import pytest

    factory = SecurityHandlerFactory.INSTANCE

    with pytest.raises(RuntimeError, match="already registered"):
        factory.register_handler(
            StandardSecurityHandler.FILTER,
            StandardSecurityHandler,
            StandardProtectionPolicy,
        )
