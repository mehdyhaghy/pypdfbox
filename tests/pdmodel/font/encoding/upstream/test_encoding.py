"""Ported upstream-style tests for the base ``Encoding`` class.

Upstream PDFBox 3.0 has no dedicated ``EncodingTest.java`` for the abstract
base — its surface is exercised through subclass tests. These tests exercise
the contract the abstract base defines: bidirectional name <-> code lookup,
``.notdef`` fallback, ``contains`` membership, and the ``add`` /
``overwrite`` semantics that mirror Java's ``Map.putIfAbsent``.
"""

from __future__ import annotations

from pypdfbox.cos import COSName
from pypdfbox.pdmodel.font.encoding import (
    Encoding,
    MacExpertEncoding,
    MacRomanEncoding,
    StandardEncoding,
    SymbolEncoding,
    WinAnsiEncoding,
    ZapfDingbatsEncoding,
)


# -- factory ---------------------------------------------------------------


def test_get_instance_resolves_all_six_predefined_encodings():
    pairs = [
        ("StandardEncoding", StandardEncoding.INSTANCE),
        ("WinAnsiEncoding", WinAnsiEncoding.INSTANCE),
        ("MacRomanEncoding", MacRomanEncoding.INSTANCE),
        ("MacExpertEncoding", MacExpertEncoding.INSTANCE),
        ("SymbolEncoding", SymbolEncoding.INSTANCE),
        ("ZapfDingbatsEncoding", ZapfDingbatsEncoding.INSTANCE),
    ]
    for name, expected in pairs:
        assert Encoding.get_instance(name) is expected
        assert Encoding.get_instance(COSName.get_pdf_name(name)) is expected


def test_get_instance_returns_singleton_each_call():
    a = Encoding.get_instance("WinAnsiEncoding")
    b = Encoding.get_instance("WinAnsiEncoding")
    assert a is b


# -- get_name / get_code ---------------------------------------------------


def test_get_name_returns_notdef_for_unmapped():
    # Upstream getName(int) never returns null — it returns ".notdef".
    assert StandardEncoding.INSTANCE.get_name(0x01) == ".notdef"


def test_get_name_no_arg_returns_encoding_identifier():
    assert StandardEncoding.INSTANCE.get_name() == "StandardEncoding"
    assert WinAnsiEncoding.INSTANCE.get_name() == "WinAnsiEncoding"


def test_get_code_returns_int_for_known_glyph():
    assert StandardEncoding.INSTANCE.get_code("A") == 0x41


def test_get_code_returns_none_for_unknown_glyph():
    # Upstream uses Integer (boxed); null when missing. Python returns None.
    assert StandardEncoding.INSTANCE.get_code("xyzzy-not-real") is None


# -- contains --------------------------------------------------------------


def test_contains_name_true_for_mapped():
    assert WinAnsiEncoding.INSTANCE.contains_name("A") is True


def test_contains_name_false_for_unmapped():
    assert WinAnsiEncoding.INSTANCE.contains_name("xyzzy") is False


def test_contains_code_true_for_mapped():
    assert WinAnsiEncoding.INSTANCE.contains_code(0x41) is True


def test_contains_code_false_for_unmapped():
    assert WinAnsiEncoding.INSTANCE.contains_code(0x01) is False


def test_polymorphic_contains():
    enc = WinAnsiEncoding.INSTANCE
    assert enc.contains("A") is True
    assert enc.contains(0x41) is True
    assert enc.contains("xyzzy") is False


# -- snapshot maps ---------------------------------------------------------


def test_get_code_to_name_map_returns_snapshot():
    enc = StandardEncoding.INSTANCE
    m = enc.get_code_to_name_map()
    m[0xFF] = "BOGUS"
    # Mutating the snapshot does not affect the encoding.
    assert enc.get_name(0xFF) != "BOGUS" or enc.get_name(0xFF) == ".notdef"


def test_get_name_to_code_map_returns_snapshot():
    enc = WinAnsiEncoding.INSTANCE
    m = enc.get_name_to_code_map()
    assert m["A"] == 0x41
    m["A"] = 0xFF
    # Original singleton is unaffected.
    assert enc.get_code("A") == 0x41


# -- add / overwrite semantics ---------------------------------------------


def test_add_keeps_first_reverse_mapping():
    # Java's Map.putIfAbsent semantics — the first code that maps to a glyph
    # wins for the reverse lookup.
    enc = Encoding()
    enc.add(0x41, "A")
    enc.add(0x61, "A")  # lowercase 'a' position also maps to "A"
    assert enc.get_name(0x41) == "A"
    assert enc.get_name(0x61) == "A"
    # Reverse map keeps the first inserted code.
    assert enc.get_code("A") == 0x41


def test_overwrite_replaces_reverse_mapping():
    enc = Encoding()
    enc.add(0x41, "A")
    # Now overwrite slot 0x41 with a different glyph; the orphaned reverse
    # mapping for "A" must also be cleaned up.
    enc.overwrite(0x41, "Aacute")
    assert enc.get_name(0x41) == "Aacute"
    assert enc.get_code("Aacute") == 0x41
    # The displaced "A" no longer resolves to 0x41.
    assert enc.get_code("A") is None
