"""Port of upstream ``TestCMapParser`` from
``fontbox/src/test/java/org/apache/fontbox/cmap/TestCMapParser.java``.

Operator-level synthetic cases live here alongside the upstream
fixture-driven tests (``CMapTest``, ``CMapNoWhitespace``,
``CMapMalformedbfrange[12]``, ``Identitybfrange``) which were copied
verbatim into ``tests/fixtures/fontbox/cmap/``. Bundled-resource tests
that require Adobe predefined CMaps (UniJIS-UTF16-H, Adobe-GB1-UCS2,
Adobe-Korea1-UCS2) are covered separately in
``tests/fontbox/cmap/test_cmap_parser_parity.py``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.fontbox.cmap import CMapParser

_FIXTURES = Path(__file__).resolve().parents[3] / "fixtures" / "fontbox" / "cmap"


def _parser() -> CMapParser:
    return CMapParser()


def _fixture(name: str) -> bytes:
    return (_FIXTURES / name).read_bytes()


# Translated from testIdentityHorBfRange (PDFBOX-4720).
def test_identity_hor_bfrange() -> None:
    cmap = _parser().parse(
        b"""
        1 beginbfrange
        <0000> <FFFF> <0000>
        endbfrange
        endcmap
        """
    )

    assert cmap.to_unicode_bytes(b"\x00\x00") == "\x00"
    assert cmap.to_unicode_bytes(b"\x00A") == "A"
    assert cmap.to_unicode_bytes(b"\xff\xff") == "\uffff"


# Translated from testPdfbox4550 -- corrupt bfrange where end < start.
def test_pdfbox4550_corrupt_bfrange_aborts() -> None:
    cmap = _parser().parse(
        b"""
        1 begincodespacerange <00> <FF> endcodespacerange
        1 beginbfrange
        <44> <42> <0041>
        endbfrange
        endcmap
        """
    )
    assert cmap.to_unicode_bytes(b"\x42") is None
    assert cmap.to_unicode_bytes(b"\x44") is None


# Translated from testPdfbox3807 -- null-typed mapping value is silently
# skipped without crashing.
def test_pdfbox3807_null_mapping_value_ignored() -> None:
    # Use an integer in place of the string/array dst; parser should drop
    # the entry and continue rather than blow up.
    cmap = _parser().parse(
        b"""
        1 begincodespacerange <00> <FF> endcodespacerange
        1 beginbfrange
        <01> <02> 99
        endbfrange
        endcmap
        """
    )
    assert cmap.to_unicode_bytes(b"\x01") is None


# Translated from testCMapMalformed -- tabs / odd whitespace are tolerated.
def test_cmap_tolerates_tab_separated_codespace() -> None:
    cmap = _parser().parse(
        b"1 begincodespacerange\n<00>\t<ff>\nendcodespacerange\nendcmap\n"
    )
    assert cmap.code_length_at(0x40) == 1


# Translated from testNotDefRange -- beginnotdefrange registers the
# substitute CID for every code in the range.
def test_notdef_range_assigns_substitute_cid() -> None:
    cmap = _parser().parse(
        b"""
        1 begincodespacerange <0000> <FFFF> endcodespacerange
        1 beginnotdefrange
        <0001> <0005> 9999
        endnotdefrange
        endcmap
        """
    )
    for code in range(1, 6):
        assert cmap.to_cid_bytes(bytes([0x00, code])) == 9999


# Translated from testCidRange -- increments the dst CID across the range.
def test_cid_range_increments() -> None:
    cmap = _parser().parse(
        b"""
        1 begincodespacerange <0000> <FFFF> endcodespacerange
        1 begincidrange
        <0010> <0012> 100
        endcidrange
        endcmap
        """
    )
    assert cmap.to_cid_bytes(b"\x00\x10") == 100
    assert cmap.to_cid_bytes(b"\x00\x11") == 101
    assert cmap.to_cid_bytes(b"\x00\x12") == 102


# Translated from testCMapHeaders -- Registry/Ordering/Supplement.
def test_cmap_header_fields_round_trip() -> None:
    cmap = _parser().parse(
        b"""
        /CMapName /Test-Headers def
        /CMapType 2 def
        /Registry (Adobe) def
        /Ordering (Japan1) def
        /Supplement 6 def
        /WMode 1 def
        endcmap
        """
    )
    assert cmap.get_name() == "Test-Headers"
    assert cmap.get_type() == 2
    assert cmap.get_registry() == "Adobe"
    assert cmap.get_ordering() == "Japan1"
    assert cmap.get_supplement() == 6
    assert cmap.get_wmode() == 1


# Translated from testUseCMap -- usecmap directive cascades from a
# referenced predefined CMap.
def test_usecmap_inherits_codespaces_from_identity_h() -> None:
    cmap = _parser().parse(
        b"""
        /Identity-H usecmap
        endcmap
        """
    )
    # Identity-H provides the 0..0xFFFF CID range.
    assert cmap.to_cid_bytes(b"\xab\xcd") == 0xABCD


# Translated from testBfChar -- basic one-to-one Unicode mapping.
def test_bfchar_basic() -> None:
    cmap = _parser().parse(
        b"""
        1 begincodespacerange <00> <FF> endcodespacerange
        1 beginbfchar
        <20> <0020>
        endbfchar
        endcmap
        """
    )
    assert cmap.to_unicode_bytes(b"\x20") == " "
    # Space mapping is tracked separately on the CMap.
    assert cmap.get_space_mapping() == 0x20


# Translated from testEndCMapTerminatesParse -- endcmap stops the parser
# even when more bytes follow.
def test_endcmap_stops_parse() -> None:
    payload = (
        b"1 begincodespacerange <00> <FF> endcodespacerange\n"
        b"endcmap\n"
        b"% these tokens must NOT influence the result\n"
        b"1 beginbfchar <20> <0020> endbfchar\n"
    )
    cmap = _parser().parse(payload)
    # bfchar after endcmap is ignored.
    assert cmap.to_unicode_bytes(b"\x20") is None


# Translated from testParseUnicodeCMapMissingThrows -- missing bytes
# raise an OSError.
def test_parse_unicode_cmap_none_raises() -> None:
    with pytest.raises(OSError):
        _parser().parse_unicode_cmap(None)  # type: ignore[arg-type]


# ---------- fixture-driven upstream tests (TestCMapParser.java) ----------


# Translated from testLookup -- exhaustive check of bfchar / bfrange /
# cidchar / cidrange / single-value cidrange against the canonical
# CMapTest fixture.
def test_lookup() -> None:
    cmap = _parser().parse(_fixture("CMapTest"))

    # char mappings
    assert cmap.to_unicode_bytes(bytes([0, 1])) == "A"
    assert cmap.to_unicode_bytes(bytes([1, 0])) == "0"
    assert cmap.to_unicode_bytes(bytes([1, 32])) == "P"
    assert cmap.to_unicode_bytes(bytes([1, 33])) == "R"
    assert cmap.to_unicode_bytes(bytes([0, 10])) == "*"
    assert cmap.to_unicode_bytes(bytes([1, 10])) == "+"

    # CID mappings
    assert cmap.to_cid_bytes(bytes([0, 65])) == 65
    assert cmap.to_cid_bytes(bytes([1, 24])) == 0x0118
    assert cmap.to_cid_bytes(bytes([2, 8])) == 0x0208
    assert cmap.to_cid_bytes(bytes([1, 0x2C])) == 0x12C


# Translated from testIdentity.
def test_identity() -> None:
    cmap = CMapParser.parse_predefined("Identity-H")

    assert cmap.to_cid_bytes(bytes([0, 65])) == 65
    assert cmap.to_cid_bytes(bytes([0x30, 0x39])) == 12345
    assert cmap.to_cid_bytes(bytes([0xFF, 0xFF])) == 0xFFFF


# Translated from testParserWithPoorWhitespace -- the CMapNoWhitespace
# fixture is a structurally-valid CMap with deliberately gnarly
# whitespace; parsing must not abort.
def test_parser_with_poor_whitespace() -> None:
    cmap = _parser().parse(_fixture("CMapNoWhitespace"))
    assert cmap is not None


# Translated from testParserWithMalformedbfrange1.
def test_parser_with_malformed_bfrange1() -> None:
    cmap = _parser().parse(_fixture("CMapMalformedbfrange1"))
    assert cmap is not None
    assert cmap.to_unicode_bytes(bytes([0, 1])) == "A"
    assert cmap.to_unicode_bytes(bytes([1, 0])) is None


# Translated from testParserWithMalformedbfrange2 -- exercises both the
# default permissive mode and strict mode (PDFBOX-4661 / PDFBOX-5090).
def test_parser_with_malformed_bfrange2() -> None:
    payload = _fixture("CMapMalformedbfrange2")
    cmap = _parser().parse(payload)
    assert cmap is not None
    assert cmap.to_unicode_bytes(bytes([0, 1])) == "0"
    assert cmap.to_unicode_bytes(bytes([2, 0x32])) == "A"

    # Permissive mode: low-byte overflow extends past 0xF0.
    assert cmap.to_unicode_bytes(bytes([2, 0xF0])) is not None
    assert cmap.to_unicode_bytes(bytes([2, 0xF1])) is not None

    # Strict mode rejects the overflowed mapping at 0xF1 (last legal value
    # is 0xF0; one past triggers PDFBOX-5090's overflow guard).
    cmap_strict = CMapParser(strict_mode=True).parse(payload)
    assert cmap_strict.to_unicode_bytes(bytes([2, 0xF0])) is not None
    assert cmap_strict.to_unicode_bytes(bytes([2, 0xF1])) is None


# Translated from testIdentitybfrange -- a strict-mode parse of a
# bfrange covering 0x0000..0xFFFF where the dst is also identity.
def test_identity_bfrange() -> None:
    cmap = CMapParser(strict_mode=True).parse(_fixture("Identitybfrange"))
    assert cmap.get_name() == "Adobe-Identity-UCS"

    for code in (
        bytes([0, 65]),
        bytes([0x30, 0x39]),
        bytes([0x30, 0xFF]),
        bytes([0x31, 0x00]),
        bytes([0xFF, 0xFF]),
    ):
        assert cmap.to_unicode_bytes(code) == code.decode("utf-16-be")


# Translated from testBadIncrement -- empty hex strings produce zero-
# length byte arrays; the increment helper must not throw an
# IndexOutOfBounds for position -1.
def test_bad_increment() -> None:
    cmap_data = b"1 beginbfrange\n<> <> <2223>\nendbfrange"
    cmap = _parser().parse(cmap_data)
    assert cmap is not None
