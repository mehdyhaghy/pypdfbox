"""Hand-written tests for the pdmodel ``SymbolEncoding`` wrapper.

The Symbol encoding maps the Greek alphabet and math operators; the ASCII
range carries Greek-style glyph names rather than Latin.
"""

from __future__ import annotations

from pypdfbox.cos import COSName
from pypdfbox.pdmodel.font.encoding import Encoding, SymbolEncoding


def test_singleton_identity():
    assert SymbolEncoding.INSTANCE is SymbolEncoding.INSTANCE
    assert isinstance(SymbolEncoding.INSTANCE, SymbolEncoding)


def test_encoding_name():
    assert SymbolEncoding.INSTANCE.get_encoding_name() == "SymbolEncoding"


def test_get_cos_object():
    cos = SymbolEncoding.INSTANCE.get_cos_object()
    assert isinstance(cos, COSName)
    assert cos.name == "SymbolEncoding"


def test_get_cos_object_is_stable():
    # Upstream's explicit override returns ``COSName.getPDFName(...)`` which
    # is interned — repeated calls must produce the same ``COSName`` object.
    enc = SymbolEncoding.INSTANCE
    assert enc.get_cos_object() is enc.get_cos_object()


def test_greek_capitals_are_mapped():
    enc = SymbolEncoding.INSTANCE
    # 0x41 = 'A' position is "Alpha" in Symbol encoding.
    assert enc.get_name(0o101) == "Alpha"
    assert enc.get_name(0o102) == "Beta"
    assert enc.get_name(0o104) == "Delta"


def test_euro_glyph():
    # PDFBox's Symbol table assigns Euro at 0o240.
    assert SymbolEncoding.INSTANCE.get_name(0o240) == "Euro"


def test_round_trip_get_code():
    enc = SymbolEncoding.INSTANCE
    assert enc.get_code("Alpha") == 0o101
    assert enc.get_code("Beta") == 0o102


def test_does_not_contain_latin_a():
    # Symbol carries "Alpha" in the 'A' code slot, not "A".
    assert SymbolEncoding.INSTANCE.contains_name("A") is False
    # ...but does contain "Alpha".
    assert SymbolEncoding.INSTANCE.contains_name("Alpha") is True


def test_factory_resolves_to_singleton():
    assert Encoding.get_instance("SymbolEncoding") is SymbolEncoding.INSTANCE
    assert Encoding.get_instance(COSName.get_pdf_name("SymbolEncoding")) is SymbolEncoding.INSTANCE


def test_table_is_non_empty():
    assert len(SymbolEncoding.INSTANCE.get_code_to_name_map()) > 100
