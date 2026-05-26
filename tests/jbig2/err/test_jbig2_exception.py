from __future__ import annotations

import pytest

from pypdfbox.jbig2.err.integer_max_value_exception import IntegerMaxValueException
from pypdfbox.jbig2.err.invalid_header_value_exception import InvalidHeaderValueException
from pypdfbox.jbig2.err.jbig2_exception import JBIG2Exception


def test_jbig2_exception_is_exception_not_oserror() -> None:
    # Upstream extends java.lang.Exception, not IOException -> plain Exception.
    assert issubclass(JBIG2Exception, Exception)
    assert not issubclass(JBIG2Exception, OSError)


def test_no_arg_construction() -> None:
    exc = JBIG2Exception()
    assert str(exc) == ""
    assert exc.__cause__ is None


def test_message_construction() -> None:
    exc = JBIG2Exception("boom")
    assert str(exc) == "boom"
    assert exc.args == ("boom",)


def test_cause_construction() -> None:
    cause = ValueError("root")
    exc = JBIG2Exception(cause=cause)
    assert exc.__cause__ is cause


def test_message_and_cause_construction() -> None:
    cause = ValueError("root")
    exc = JBIG2Exception("boom", cause=cause)
    assert str(exc) == "boom"
    assert exc.__cause__ is cause


def test_raise_and_catch() -> None:
    with pytest.raises(JBIG2Exception) as info:
        raise JBIG2Exception("bad jbig2")
    assert str(info.value) == "bad jbig2"


def test_integer_max_value_exception_inheritance() -> None:
    assert issubclass(IntegerMaxValueException, JBIG2Exception)
    exc = IntegerMaxValueException("too big")
    assert isinstance(exc, JBIG2Exception)
    assert str(exc) == "too big"


def test_invalid_header_value_exception_inheritance() -> None:
    assert issubclass(InvalidHeaderValueException, JBIG2Exception)
    exc = InvalidHeaderValueException("bad header")
    assert isinstance(exc, JBIG2Exception)
    assert str(exc) == "bad header"


def test_subclasses_are_distinct() -> None:
    assert not issubclass(IntegerMaxValueException, InvalidHeaderValueException)
    assert not issubclass(InvalidHeaderValueException, IntegerMaxValueException)


def test_subclass_caught_as_base() -> None:
    with pytest.raises(JBIG2Exception):
        raise IntegerMaxValueException("overflow")
    with pytest.raises(JBIG2Exception):
        raise InvalidHeaderValueException("nope")


def test_subclass_cause_chaining() -> None:
    cause = OSError("io")
    exc = InvalidHeaderValueException("bad header", cause=cause)
    assert exc.__cause__ is cause


def test_subclass_no_arg() -> None:
    assert str(IntegerMaxValueException()) == ""
    assert str(InvalidHeaderValueException()) == ""
