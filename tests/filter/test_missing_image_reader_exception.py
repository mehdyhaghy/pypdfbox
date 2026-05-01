from __future__ import annotations

import pytest

from pypdfbox.filter import MissingImageReaderException


def test_message_round_trips_through_str() -> None:
    exc = MissingImageReaderException("Cannot read JPEG2000 image: no decoder")
    assert str(exc) == "Cannot read JPEG2000 image: no decoder"


def test_args_preserves_message() -> None:
    exc = MissingImageReaderException("Cannot read TIFF image: no decoder")
    assert exc.args == ("Cannot read TIFF image: no decoder",)


def test_is_oserror_subclass() -> None:
    # Upstream extends IOException; per CLAUDE.md we map IOException to OSError.
    assert issubclass(MissingImageReaderException, OSError)


def test_can_be_raised_and_caught_as_oserror() -> None:
    with pytest.raises(OSError) as info:
        raise MissingImageReaderException("Cannot read JPEG2000 image: no decoder")
    assert isinstance(info.value, MissingImageReaderException)


def test_empty_message_is_allowed() -> None:
    exc = MissingImageReaderException("")
    assert str(exc) == ""


def test_re_raise_preserves_type() -> None:
    try:
        raise MissingImageReaderException("Cannot read JBIG2 image: missing")
    except MissingImageReaderException as exc:
        assert "JBIG2" in str(exc)
