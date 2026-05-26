"""Tests for ``DamagedFontException`` (fontbox ``type1``).

Upstream has no standalone ``DamagedFontExceptionTest.java``; the class is
only exercised indirectly via ``Type1LexerTest``. These hand-written tests
cover construction, message round-trip, inheritance, and raise/catch.
"""

from __future__ import annotations

import pytest

from pypdfbox.fontbox.type1 import DamagedFontException as DamagedFontExceptionReexport
from pypdfbox.fontbox.type1.damaged_font_exception import DamagedFontException


def test_subclasses_oserror():
    # Upstream extends IOException -> OSError per repo convention.
    assert issubclass(DamagedFontException, OSError)


def test_package_reexport_is_same_class():
    assert DamagedFontExceptionReexport is DamagedFontException


def test_message_round_trips():
    exc = DamagedFontException("Could not read token at position 42")
    assert str(exc) == "Could not read token at position 42"
    assert exc.args == ("Could not read token at position 42",)


def test_raises_and_catches():
    with pytest.raises(DamagedFontException, match="corrupt"):
        raise DamagedFontException("stream is corrupt")


def test_catchable_as_oserror():
    # Callers that catch IOException upstream should catch this via OSError.
    with pytest.raises(OSError):
        raise DamagedFontException("damaged")
