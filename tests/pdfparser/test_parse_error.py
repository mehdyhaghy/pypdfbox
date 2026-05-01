from __future__ import annotations

import pytest

from pypdfbox.pdfparser.parse_error import PDFParseError


def test_message_only():
    err = PDFParseError("boom")
    assert str(err) == "boom"
    assert err.position is None
    assert err.message == "boom"
    assert err.get_message() == "boom"
    assert err.get_position() is None
    assert err.cause is None
    assert err.get_cause() is None


def test_message_with_position():
    err = PDFParseError("bad token", position=42)
    assert str(err) == "bad token (at byte 42)"
    assert err.position == 42
    assert err.get_position() == 42
    # Raw message is preserved without the byte-offset suffix.
    assert err.message == "bad token"
    assert err.get_message() == "bad token"


def test_position_zero_is_recorded():
    # Position 0 is a legitimate byte offset — must not be conflated
    # with "unknown" (which is ``None``).
    err = PDFParseError("at start", position=0)
    assert err.position == 0
    assert err.get_position() == 0
    assert "(at byte 0)" in str(err)


def test_cause_chains_via_dunder_cause():
    inner = OSError("disk dead")
    err = PDFParseError("read failed", cause=inner)
    assert err.cause is inner
    assert err.get_cause() is inner
    # Wired into __cause__ so ``raise ... from cause`` style chaining is
    # automatic when the helper constructor is used directly.
    assert err.__cause__ is inner


def test_existing_dunder_cause_not_overwritten():
    inner = ValueError("first")
    other = RuntimeError("second")
    err = PDFParseError("wrap", cause=inner)
    err.__cause__ = other
    # If __cause__ was already populated (e.g. by a prior ``from``),
    # the constructor must not stomp it. We confirm that by re-running
    # the constructor logic via a fresh instance.
    fresh = PDFParseError("again", cause=inner)
    assert fresh.__cause__ is inner
    # And the manually-set value on ``err`` survives.
    assert err.__cause__ is other


def test_with_position_preserves_message_and_cause():
    inner = OSError("io")
    base = PDFParseError("oops", cause=inner)
    enriched = base.with_position(99)
    assert enriched is not base
    assert enriched.position == 99
    assert enriched.message == "oops"
    assert enriched.get_cause() is inner
    assert str(enriched) == "oops (at byte 99)"


def test_is_a_value_error():
    # PDFParseError extends ValueError so blanket ``except ValueError``
    # in caller recovery code keeps working.
    err = PDFParseError("malformed")
    assert isinstance(err, ValueError)


def test_raises_via_pytest():
    with pytest.raises(PDFParseError) as excinfo:
        raise PDFParseError("nope", position=7)
    assert excinfo.value.get_position() == 7
    assert excinfo.value.get_message() == "nope"
