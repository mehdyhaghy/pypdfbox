from __future__ import annotations

from pypdfbox.fontbox.encoding import SymbolEncoding


def test_singleton_instance() -> None:
    assert SymbolEncoding.INSTANCE is SymbolEncoding.INSTANCE


def test_encoding_name() -> None:
    assert SymbolEncoding.INSTANCE.get_encoding_name() == "SymbolEncoding"


def test_greek_letters() -> None:
    enc = SymbolEncoding.INSTANCE
    assert enc.get_name(0o101) == "Alpha"
    assert enc.get_name(0o102) == "Beta"
    assert enc.get_name(0o141) == "alpha"
    assert enc.get_name(0o142) == "beta"


def test_round_trip() -> None:
    enc = SymbolEncoding.INSTANCE
    for name in ["Alpha", "alpha", "infinity", "integral", "summation", "Euro"]:
        code = enc.get_code(name)
        assert code is not None
        assert enc.get_name(code) == name


def test_unmapped_returns_notdef() -> None:
    enc = SymbolEncoding.INSTANCE
    assert enc.get_name(0) == ".notdef"


def test_euro_at_0o240() -> None:
    enc = SymbolEncoding.INSTANCE
    assert enc.get_name(0o240) == "Euro"
