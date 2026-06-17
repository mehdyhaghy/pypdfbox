from __future__ import annotations

from pypdfbox.fontbox.encoding import MacRomanEncoding


def test_singleton_instance() -> None:
    assert MacRomanEncoding.INSTANCE is MacRomanEncoding.INSTANCE


def test_encoding_name() -> None:
    assert MacRomanEncoding.INSTANCE.get_encoding_name() == "MacRomanEncoding"


def test_known_mappings() -> None:
    enc = MacRomanEncoding.INSTANCE
    assert enc.get_name(32) == "space"
    assert enc.get_name(65) == "A"
    assert enc.get_name(112) == "p"
    assert enc.get_name(167) == "germandbls"


def test_round_trip() -> None:
    enc = MacRomanEncoding.INSTANCE
    assert enc.get_code("space") == 32
    assert enc.get_code("A") == 65
    assert enc.get_code("germandbls") == 167


def test_unmapped_returns_notdef() -> None:
    enc = MacRomanEncoding.INSTANCE
    # 0 not in table
    assert enc.get_name(0) == ".notdef"


def test_table_size() -> None:
    # 208 entries from the upstream MacRomanEncoding table: 207 spec rows
    # plus the PDFBox-specific 0o312 ("nbspace") entry.
    assert len(MacRomanEncoding.INSTANCE.get_codes()) == 208
