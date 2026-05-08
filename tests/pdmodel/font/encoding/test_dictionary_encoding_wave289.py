from __future__ import annotations

from pypdfbox.cos import COSArray, COSInteger, COSName
from pypdfbox.pdmodel.font.encoding import DictionaryEncoding


def test_has_differences_requires_cos_array() -> None:
    enc = DictionaryEncoding()
    assert enc.has_differences() is False

    enc.get_cos_object().set_item(
        COSName.get_pdf_name("Differences"),
        COSName.get_pdf_name("not-an-array"),
    )

    assert enc.has_differences() is False
    assert enc.get_differences_array() is None


def test_clear_differences_removes_entry_and_restores_base_mapping() -> None:
    enc = DictionaryEncoding(base_encoding=COSName.get_pdf_name("WinAnsiEncoding"))
    enc.set_differences({0x41: "customGlyph"})
    assert enc.has_differences() is True
    assert enc.get_name(0x41) == "customGlyph"

    enc.clear_differences()

    assert enc.has_differences() is False
    assert enc.get_differences() == {}
    assert enc.get_differences_array() is None
    assert enc.get_name(0x41) == "A"
    assert enc.get_code("A") == 0x41
    assert enc.get_code("customGlyph") is None


def test_set_differences_replaces_stale_overlay_and_reverse_mapping() -> None:
    enc = DictionaryEncoding(base_encoding=COSName.get_pdf_name("WinAnsiEncoding"))
    enc.set_differences({0x41: "customGlyph"})

    enc.set_differences({0x42: "Acircumflex"})

    assert enc.get_differences() == {0x42: "Acircumflex"}
    assert enc.get_name(0x41) == "A"
    assert enc.get_code("A") == 0x41
    assert enc.get_code("customGlyph") is None
    assert enc.get_name(0x42) == "Acircumflex"


def test_set_differences_cos_array_rebuilds_from_base() -> None:
    enc = DictionaryEncoding(base_encoding=COSName.get_pdf_name("WinAnsiEncoding"))
    enc.set_differences({0x41: "Aacute"})

    diffs = COSArray()
    diffs.add(COSInteger.get(0x42))
    diffs.add(COSName.get_pdf_name("Acircumflex"))
    enc.set_differences(diffs)

    assert enc.get_differences_array() is diffs
    assert enc.get_name(0x41) == "A"
    assert enc.get_name(0x42) == "Acircumflex"


def test_set_base_encoding_rebuilds_base_but_preserves_differences() -> None:
    enc = DictionaryEncoding()
    enc.set_differences({0x41: "Aacute"})
    assert enc.get_name(0x61) == ".notdef"

    enc.set_base_encoding("WinAnsiEncoding")

    assert enc.get_name(0x61) == "a"
    assert enc.get_name(0x41) == "Aacute"
    assert enc.get_differences() == {0x41: "Aacute"}
