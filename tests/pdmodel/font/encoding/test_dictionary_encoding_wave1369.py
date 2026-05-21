"""DictionaryEncoding override semantics across all four /BaseEncoding values.

Wave 1369 round-out for the /Differences inheritance matrix — exercises the
StandardEncoding/WinAnsiEncoding/MacRomanEncoding/MacExpertEncoding base
fall-through plus the writer-side /Differences write-back round-trip via
``set_differences``/``clear_differences``/``set_base_encoding``.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName
from pypdfbox.pdmodel.font.encoding import (
    DictionaryEncoding,
    Encoding,
    MacExpertEncoding,
    MacRomanEncoding,
    StandardEncoding,
    WinAnsiEncoding,
)

# Per PDF 32000-1 §D the four predefined PDF encodings all share /space at 0x20
# and /A at 0x41 — those code points are the safe parametrise probes.
_BASES = [
    ("StandardEncoding", StandardEncoding.INSTANCE),
    ("WinAnsiEncoding", WinAnsiEncoding.INSTANCE),
    ("MacRomanEncoding", MacRomanEncoding.INSTANCE),
    ("MacExpertEncoding", MacExpertEncoding.INSTANCE),
]


@pytest.mark.parametrize("base_name,base_instance", _BASES)
def test_writer_path_inherits_from_each_predefined_base(
    base_name: str, base_instance: Encoding
) -> None:
    enc = DictionaryEncoding(base_encoding=COSName.get_pdf_name(base_name))
    assert enc.get_base_encoding() is base_instance
    cos = enc.get_cos_object()
    assert cos.get_name(COSName.get_pdf_name("BaseEncoding")) == base_name
    # Code 0x20 is /space in all four predefined encodings (PDF 32000-1 Annex D).
    if base_instance.contains_code(0x20):
        assert enc.get_name(0x20) == base_instance.get_name(0x20)


@pytest.mark.parametrize("base_name,base_instance", _BASES)
def test_differences_overlay_on_top_of_each_predefined_base(
    base_name: str, base_instance: Encoding
) -> None:
    diffs = COSArray()
    diffs.add(COSInteger.get(0x80))
    diffs.add(COSName.get_pdf_name("custom_glyph_one"))
    diffs.add(COSName.get_pdf_name("custom_glyph_two"))
    enc = DictionaryEncoding(
        base_encoding=COSName.get_pdf_name(base_name),
        differences=diffs,
    )
    # Differences win at the overlapping codes.
    assert enc.get_name(0x80) == "custom_glyph_one"
    assert enc.get_name(0x81) == "custom_glyph_two"
    # Codes outside the differences range still flow from the base.
    if base_instance.contains_code(0x41):
        assert enc.get_name(0x41) == base_instance.get_name(0x41)


def test_get_encoding_name_format_matches_upstream() -> None:
    # "<base> with differences" — Type 3 / no-base returns just "differences".
    enc_with_base = DictionaryEncoding(
        base_encoding=COSName.get_pdf_name("StandardEncoding")
    )
    assert enc_with_base.get_encoding_name() == "StandardEncoding with differences"
    enc_type3 = DictionaryEncoding(font_encoding=COSDictionary())
    assert enc_type3.get_encoding_name() == "differences"


def test_set_base_encoding_via_string_swaps_inheritance() -> None:
    enc = DictionaryEncoding(base_encoding=COSName.get_pdf_name("WinAnsiEncoding"))
    assert enc.get_base_encoding() is WinAnsiEncoding.INSTANCE
    enc.set_base_encoding("MacRomanEncoding")
    assert enc.get_base_encoding() is MacRomanEncoding.INSTANCE
    # The COS dict reflects the new base.
    cos = enc.get_cos_object()
    assert cos.get_name(COSName.get_pdf_name("BaseEncoding")) == "MacRomanEncoding"


def test_set_base_encoding_via_encoding_object() -> None:
    enc = DictionaryEncoding(base_encoding=COSName.get_pdf_name("WinAnsiEncoding"))
    enc.set_base_encoding(MacExpertEncoding.INSTANCE)
    assert enc.get_base_encoding() is MacExpertEncoding.INSTANCE


def test_set_base_encoding_to_none_clears_entry() -> None:
    enc = DictionaryEncoding(base_encoding=COSName.get_pdf_name("WinAnsiEncoding"))
    enc.set_base_encoding(None)
    assert enc.get_base_encoding() is None
    assert enc.is_type3() is True
    assert enc.has_base_encoding() is False
    cos = enc.get_cos_object()
    assert cos.get_dictionary_object(COSName.get_pdf_name("BaseEncoding")) is None


def test_set_base_encoding_invalid_string_raises() -> None:
    enc = DictionaryEncoding()
    with pytest.raises(ValueError):
        enc.set_base_encoding("DoesNotExistEncoding")


def test_clear_differences_restores_base_view() -> None:
    diffs = COSArray()
    diffs.add(COSInteger.get(0x41))
    diffs.add(COSName.get_pdf_name("custom"))
    enc = DictionaryEncoding(
        base_encoding=COSName.get_pdf_name("WinAnsiEncoding"),
        differences=diffs,
    )
    assert enc.get_name(0x41) == "custom"
    assert enc.has_differences() is True
    enc.clear_differences()
    # After clear we see the WinAnsi base mapping again (0x41 -> "A").
    assert enc.get_name(0x41) == "A"
    assert enc.has_differences() is False


def test_set_differences_dict_form_rebuilds_view() -> None:
    enc = DictionaryEncoding(base_encoding=COSName.get_pdf_name("WinAnsiEncoding"))
    enc.set_differences({0x41: "Aacute", 0x42: "Acircumflex"})
    assert enc.get_name(0x41) == "Aacute"
    assert enc.get_name(0x42) == "Acircumflex"
    # Round-trip via get_differences gives a snapshot of the COS-backed view.
    assert enc.get_differences() == {0x41: "Aacute", 0x42: "Acircumflex"}


def test_set_differences_array_form_rebuilds_view() -> None:
    enc = DictionaryEncoding(base_encoding=COSName.get_pdf_name("WinAnsiEncoding"))
    arr = COSArray()
    arr.add(COSInteger.get(0x80))
    arr.add(COSName.get_pdf_name("glyphX"))
    arr.add(COSName.get_pdf_name("glyphY"))
    enc.set_differences(arr)
    assert enc.get_name(0x80) == "glyphX"
    assert enc.get_name(0x81) == "glyphY"
    # The same array is the live wire form.
    assert enc.get_differences_array() is arr


def test_apply_differences_picks_up_array_mutation() -> None:
    diffs = COSArray()
    diffs.add(COSInteger.get(0x80))
    diffs.add(COSName.get_pdf_name("first"))
    enc = DictionaryEncoding(
        base_encoding=COSName.get_pdf_name("WinAnsiEncoding"),
        differences=diffs,
    )
    assert enc.get_differences() == {0x80: "first"}
    # Mutate the underlying array in place.
    diffs.add(COSName.get_pdf_name("second"))  # auto-incremented to 0x81
    enc.apply_differences()
    assert enc.get_differences() == {0x80: "first", 0x81: "second"}


def test_writer_path_rejects_invalid_base_encoding() -> None:
    with pytest.raises(ValueError):
        DictionaryEncoding(base_encoding=COSName.get_pdf_name("NotAnEncoding"))


def test_symbolic_font_without_built_in_raises() -> None:
    font_enc = COSDictionary()
    with pytest.raises(ValueError):
        DictionaryEncoding(
            font_encoding=font_enc, is_non_symbolic=False, built_in=None
        )
