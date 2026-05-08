from __future__ import annotations

import pytest

from pypdfbox.pdmodel.encryption.public_key_security_handler import (
    PublicKeySecurityHandler,
)
from pypdfbox.pdmodel.encryption.security_provider import (
    get_security_handler,
    is_registered,
)
from pypdfbox.pdmodel.encryption.standard_security_handler import (
    StandardSecurityHandler,
)


def test_security_provider_registers_standard_filter() -> None:
    assert is_registered(StandardSecurityHandler.FILTER) is True
    assert isinstance(
        get_security_handler(StandardSecurityHandler.FILTER),
        StandardSecurityHandler,
    )


def test_security_provider_registers_public_key_filter() -> None:
    assert is_registered(PublicKeySecurityHandler.FILTER) is True
    assert isinstance(
        get_security_handler(PublicKeySecurityHandler.FILTER),
        PublicKeySecurityHandler,
    )


def test_security_provider_rejects_unknown_filter() -> None:
    with pytest.raises(ValueError, match="Unsupported security handler"):
        get_security_handler("NotAFilter")
