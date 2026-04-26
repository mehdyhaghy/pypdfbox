from __future__ import annotations

from pypdfbox.fontbox.encoding import ZapfDingbatsEncoding


def test_singleton_instance() -> None:
    assert ZapfDingbatsEncoding.INSTANCE is ZapfDingbatsEncoding.INSTANCE


def test_encoding_name() -> None:
    assert (
        ZapfDingbatsEncoding.INSTANCE.get_encoding_name() == "ZapfDingbatsEncoding"
    )


def test_known_mappings() -> None:
    enc = ZapfDingbatsEncoding.INSTANCE
    assert enc.get_name(0o40) == "space"
    assert enc.get_name(0o41) == "a1"
    assert enc.get_name(0o376) == "a191"


def test_round_trip() -> None:
    enc = ZapfDingbatsEncoding.INSTANCE
    for name in ["a1", "a10", "a100", "a191"]:
        code = enc.get_code(name)
        assert code is not None
        assert enc.get_name(code) == name


def test_unmapped_returns_notdef() -> None:
    enc = ZapfDingbatsEncoding.INSTANCE
    assert enc.get_name(0) == ".notdef"
    # 0o160 is "a203" — but, e.g. 0o360 is unused
    assert enc.get_name(0o360) == ".notdef"
