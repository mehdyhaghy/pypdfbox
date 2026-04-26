from __future__ import annotations

from pypdfbox.fontbox.encoding import StandardEncoding


def test_singleton_instance_exists() -> None:
    assert StandardEncoding.INSTANCE is StandardEncoding.INSTANCE


def test_encoding_name() -> None:
    assert StandardEncoding.INSTANCE.get_encoding_name() == "StandardEncoding"


def test_known_mappings() -> None:
    enc = StandardEncoding.INSTANCE
    assert enc.get_name(0o40) == "space"
    assert enc.get_name(0o101) == "A"
    assert enc.get_name(0o141) == "a"
    assert enc.get_name(0o60) == "zero"


def test_round_trip_known_names() -> None:
    enc = StandardEncoding.INSTANCE
    for name in ["A", "a", "space", "zero", "Lslash", "ampersand"]:
        code = enc.get_code(name)
        assert code is not None
        assert enc.get_name(code) == name


def test_unmapped_code_returns_notdef() -> None:
    enc = StandardEncoding.INSTANCE
    # Standard encoding has no entry for 0
    assert enc.get_name(0) == ".notdef"


def test_table_size_is_149() -> None:
    # 149 explicit (code, name) entries per upstream StandardEncoding table
    assert len(StandardEncoding.INSTANCE.get_codes()) == 149
