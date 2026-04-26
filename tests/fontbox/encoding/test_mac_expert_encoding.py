from __future__ import annotations

from pypdfbox.fontbox.encoding import MacExpertEncoding


def test_singleton_instance() -> None:
    assert MacExpertEncoding.INSTANCE is MacExpertEncoding.INSTANCE


def test_encoding_name() -> None:
    assert MacExpertEncoding.INSTANCE.get_encoding_name() == "MacExpertEncoding"


def test_known_mappings() -> None:
    enc = MacExpertEncoding.INSTANCE
    assert enc.get_name(0o276) == "AEsmall"
    assert enc.get_name(0o141) == "Asmall"
    assert enc.get_name(0o40) == "space"


def test_round_trip() -> None:
    enc = MacExpertEncoding.INSTANCE
    for name in ["AEsmall", "Asmall", "fi", "fl", "ff", "ffi"]:
        code = enc.get_code(name)
        assert code is not None
        assert enc.get_name(code) == name


def test_unmapped_returns_notdef() -> None:
    enc = MacExpertEncoding.INSTANCE
    assert enc.get_name(0) == ".notdef"
