from __future__ import annotations

# Ported from
# fontbox/src/test/java/org/apache/fontbox/encoding/EncodingTest.java

from pypdfbox.fontbox.encoding import MacRomanEncoding, StandardEncoding


def test_standard_encoding() -> None:
    standard_encoding = StandardEncoding.INSTANCE
    # check some randomly chosen mappings
    assert standard_encoding.get_name(0) == ".notdef"
    assert standard_encoding.get_name(32) == "space"
    assert standard_encoding.get_name(112) == "p"
    assert standard_encoding.get_name(172) == "guilsinglleft"
    assert standard_encoding.get_code("space") == 32
    assert standard_encoding.get_code("p") == 112
    assert standard_encoding.get_code("guilsinglleft") == 172


def test_mac_roman_encoding() -> None:
    mac_roman_encoding = MacRomanEncoding.INSTANCE
    # check some randomly chosen mappings
    assert mac_roman_encoding.get_name(0) == ".notdef"
    assert mac_roman_encoding.get_name(32) == "space"
    assert mac_roman_encoding.get_name(112) == "p"
    assert mac_roman_encoding.get_name(167) == "germandbls"
    assert mac_roman_encoding.get_code("space") == 32
    assert mac_roman_encoding.get_code("p") == 112
    assert mac_roman_encoding.get_code("germandbls") == 167
