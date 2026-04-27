"""Hand-written tests for the pdmodel ``ZapfDingbatsEncoding`` wrapper.

Zapf Dingbats encodes ornaments and symbols using the ``aN`` glyph naming
convention (a1 .. a206) — the ASCII range carries dingbat names rather
than Latin letters.
"""

from __future__ import annotations

from pypdfbox.cos import COSName
from pypdfbox.pdmodel.font.encoding import Encoding, ZapfDingbatsEncoding


def test_singleton_identity():
    assert ZapfDingbatsEncoding.INSTANCE is ZapfDingbatsEncoding.INSTANCE
    assert isinstance(ZapfDingbatsEncoding.INSTANCE, ZapfDingbatsEncoding)


def test_encoding_name():
    assert ZapfDingbatsEncoding.INSTANCE.get_encoding_name() == "ZapfDingbatsEncoding"


def test_get_cos_object():
    cos = ZapfDingbatsEncoding.INSTANCE.get_cos_object()
    assert isinstance(cos, COSName)
    assert cos.name == "ZapfDingbatsEncoding"


def test_space_is_mapped():
    assert ZapfDingbatsEncoding.INSTANCE.get_name(0o40) == "space"


def test_dingbat_glyph_naming():
    enc = ZapfDingbatsEncoding.INSTANCE
    # ASCII '!' = 0o41 -> 'a1' in dingbats.
    assert enc.get_name(0o41) == "a1"
    assert enc.get_name(0o42) == "a2"


def test_does_not_contain_latin_letters():
    # ASCII range is filled with dingbat names, not Latin letters.
    enc = ZapfDingbatsEncoding.INSTANCE
    assert enc.contains_name("A") is False
    assert enc.contains_name("z") is False


def test_dingbat_names_are_present():
    enc = ZapfDingbatsEncoding.INSTANCE
    assert enc.contains_name("a1") is True
    assert enc.contains_name("space") is True


def test_round_trip_get_code():
    enc = ZapfDingbatsEncoding.INSTANCE
    assert enc.get_code("a1") == 0o41
    assert enc.get_code("a2") == 0o42
    assert enc.get_code("space") == 0o40


def test_factory_resolves_to_singleton():
    assert Encoding.get_instance("ZapfDingbatsEncoding") is ZapfDingbatsEncoding.INSTANCE
    assert (
        Encoding.get_instance(COSName.get_pdf_name("ZapfDingbatsEncoding"))
        is ZapfDingbatsEncoding.INSTANCE
    )


def test_table_is_non_empty():
    assert len(ZapfDingbatsEncoding.INSTANCE.get_code_to_name_map()) > 100
