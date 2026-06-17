from __future__ import annotations

import pytest

from pypdfbox.pdmodel import MissingResourceException


def test_message_round_trips_through_str() -> None:
    exc = MissingResourceException("Missing XObject: Im0")
    assert str(exc) == "Missing XObject: Im0"


def test_args_preserves_message() -> None:
    exc = MissingResourceException("Missing color space: CS0")
    assert exc.args == ("Missing color space: CS0",)


def test_is_oserror_subclass() -> None:
    # Upstream extends IOException; per project convention IOException maps to OSError.
    assert issubclass(MissingResourceException, OSError)


def test_can_be_raised_and_caught_as_oserror() -> None:
    with pytest.raises(OSError) as info:
        raise MissingResourceException("Missing XObject: Im0")
    assert isinstance(info.value, MissingResourceException)


def test_distinct_from_missing_image_reader_exception() -> None:
    # Both extend OSError, but neither is a subclass of the other.
    from pypdfbox.filter import MissingImageReaderException

    assert not issubclass(MissingResourceException, MissingImageReaderException)
    assert not issubclass(MissingImageReaderException, MissingResourceException)


def test_empty_message_is_allowed() -> None:
    exc = MissingResourceException("")
    assert str(exc) == ""
