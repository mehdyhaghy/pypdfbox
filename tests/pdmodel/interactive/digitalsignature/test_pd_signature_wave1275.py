"""Wave 1275 — PDSignature.get_converted_contents helper."""

from __future__ import annotations

from pypdfbox.pdmodel.interactive.digitalsignature.pd_signature import PDSignature


def test_strips_angle_bracket_delimiters() -> None:
    sig = PDSignature()
    # "<48656C6C6F>" -> b"Hello"
    result = sig.get_converted_contents(b"<48656C6C6F>")
    assert result == b"Hello"


def test_strips_paren_delimiters() -> None:
    sig = PDSignature()
    result = sig.get_converted_contents(b"(48656C6C6F)")
    assert result == b"Hello"


def test_no_delimiters_decodes_hex_directly() -> None:
    sig = PDSignature()
    result = sig.get_converted_contents(b"414243")
    assert result == b"ABC"


def test_uppercase_and_lowercase_hex() -> None:
    sig = PDSignature()
    assert sig.get_converted_contents(b"<deadbeef>") == bytes.fromhex("deadbeef")
    assert sig.get_converted_contents(b"<DEADBEEF>") == bytes.fromhex("deadbeef")


def test_empty_input_returns_empty_bytes() -> None:
    sig = PDSignature()
    assert sig.get_converted_contents(b"") == b""
    assert sig.get_converted_contents(None) == b""


def test_only_leading_delimiter_stripped() -> None:
    sig = PDSignature()
    # No trailing > -- only leading < is stripped, body parsed as is.
    result = sig.get_converted_contents(b"<4142")
    assert result == b"AB"
