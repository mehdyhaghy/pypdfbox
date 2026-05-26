"""Focused tests for ``InvalidPasswordException``.

Mirrors ``org.apache.pdfbox.pdmodel.encryption.InvalidPasswordException``.
Verifies the canonical class name, its import paths, base class, and
raise/catch behaviour.
"""

from __future__ import annotations

import pytest


def test_importable_from_canonical_module():
    """The class is importable from its one-class-per-file module."""
    from pypdfbox.pdmodel.encryption.invalid_password_exception import (
        InvalidPasswordException,
    )

    assert InvalidPasswordException.__name__ == "InvalidPasswordException"


def test_importable_from_package():
    """The class is re-exported from the encryption package."""
    from pypdfbox.pdmodel.encryption import InvalidPasswordException

    assert InvalidPasswordException.__name__ == "InvalidPasswordException"


def test_importable_from_handler_module():
    """The handler module still exposes the name for existing imports."""
    from pypdfbox.pdmodel.encryption.standard_security_handler import (
        InvalidPasswordException,
    )

    assert InvalidPasswordException.__name__ == "InvalidPasswordException"


def test_same_class_across_import_paths():
    """All import paths resolve to the exact same class object."""
    from pypdfbox.pdmodel.encryption import (
        InvalidPasswordException as from_package,
    )
    from pypdfbox.pdmodel.encryption.invalid_password_exception import (
        InvalidPasswordException as from_module,
    )
    from pypdfbox.pdmodel.encryption.standard_security_handler import (
        InvalidPasswordException as from_handler,
    )

    assert from_module is from_package
    assert from_module is from_handler


def test_subclasses_oserror():
    """Behaviour matches upstream: an I/O-style exception (OSError)."""
    from pypdfbox.pdmodel.encryption import InvalidPasswordException

    assert issubclass(InvalidPasswordException, OSError)


def test_default_message():
    """A no-arg instance carries the default password-incorrect message."""
    from pypdfbox.pdmodel.encryption import InvalidPasswordException

    exc = InvalidPasswordException()
    assert str(exc) == "Cannot decrypt PDF, the password is incorrect"


def test_custom_message():
    """A supplied message is preserved on the exception."""
    from pypdfbox.pdmodel.encryption import InvalidPasswordException

    exc = InvalidPasswordException("bad password")
    assert str(exc) == "bad password"


def test_raise_and_catch():
    """The exception raises and is catchable by its canonical name."""
    from pypdfbox.pdmodel.encryption import InvalidPasswordException

    with pytest.raises(InvalidPasswordException):
        raise InvalidPasswordException()


def test_catchable_as_oserror():
    """It can be caught via its OSError base class."""
    from pypdfbox.pdmodel.encryption import InvalidPasswordException

    with pytest.raises(OSError):
        raise InvalidPasswordException("locked")


def test_no_pd_prefixed_alias():
    """The legacy PD-prefixed name must not exist on the package."""
    import pypdfbox.pdmodel.encryption as enc

    assert not hasattr(enc, "PDInvalidPasswordException")
