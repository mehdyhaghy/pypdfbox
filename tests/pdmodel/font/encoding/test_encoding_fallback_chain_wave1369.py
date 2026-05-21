"""Custom encoding fallback chain.

Wave 1369 round-out — exercises the precedence ladder a font's encoding
walks when resolving a character code to a glyph name. The dispatch
order is /BaseEncoding name (or non-symbolic default = Standard, or
symbolic default = built-in) -> /Differences overlay -> .notdef.

Mirrors upstream PDSimpleFont.readEncoding's branch matrix.
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName
from pypdfbox.pdmodel.font.encoding import (
    BuiltInEncoding,
    DictionaryEncoding,
    MacExpertEncoding,
    StandardEncoding,
    Type1Encoding,
    WinAnsiEncoding,
)


def test_non_symbolic_with_no_base_falls_back_to_standard() -> None:
    # PDF 32000-1 §9.6.5.4 — non-symbolic fonts default to StandardEncoding
    # when /BaseEncoding is absent.
    font_enc = COSDictionary()
    font_enc.set_item(COSName.TYPE, COSName.get_pdf_name("Encoding"))
    enc = DictionaryEncoding(font_encoding=font_enc, is_non_symbolic=True)
    assert enc.get_base_encoding() is StandardEncoding.INSTANCE
    # Codes flow from StandardEncoding (0x41 -> /A).
    assert enc.get_name(0x41) == "A"


def test_symbolic_with_no_base_falls_back_to_built_in() -> None:
    # Symbolic fonts default to the font program's built-in encoding when
    # /BaseEncoding is absent.
    built_in = BuiltInEncoding({0x41: "A_symbolic", 0x42: "B_symbolic"})
    font_enc = COSDictionary()
    font_enc.set_item(COSName.TYPE, COSName.get_pdf_name("Encoding"))
    enc = DictionaryEncoding(
        font_encoding=font_enc, is_non_symbolic=False, built_in=built_in
    )
    assert enc.get_base_encoding() is built_in
    # Codes flow from the built-in.
    assert enc.get_name(0x41) == "A_symbolic"


def test_base_encoding_overrides_default_for_non_symbolic() -> None:
    # Explicit /BaseEncoding wins over the non-symbolic StandardEncoding default.
    font_enc = COSDictionary()
    font_enc.set_item(COSName.TYPE, COSName.get_pdf_name("Encoding"))
    font_enc.set_item(
        COSName.get_pdf_name("BaseEncoding"),
        COSName.get_pdf_name("WinAnsiEncoding"),
    )
    enc = DictionaryEncoding(font_encoding=font_enc, is_non_symbolic=True)
    assert enc.get_base_encoding() is WinAnsiEncoding.INSTANCE


def test_base_encoding_overrides_built_in_for_symbolic() -> None:
    # Explicit /BaseEncoding wins over the symbolic built-in default.
    built_in = BuiltInEncoding({0x41: "A_symbolic"})
    font_enc = COSDictionary()
    font_enc.set_item(COSName.TYPE, COSName.get_pdf_name("Encoding"))
    font_enc.set_item(
        COSName.get_pdf_name("BaseEncoding"),
        COSName.get_pdf_name("MacExpertEncoding"),
    )
    enc = DictionaryEncoding(
        font_encoding=font_enc, is_non_symbolic=False, built_in=built_in
    )
    assert enc.get_base_encoding() is MacExpertEncoding.INSTANCE


def test_differences_layer_overrides_base_layer() -> None:
    # /Differences sits *on top* of /BaseEncoding's mapping and wins on the
    # codes both touch.
    font_enc = COSDictionary()
    font_enc.set_item(COSName.TYPE, COSName.get_pdf_name("Encoding"))
    font_enc.set_item(
        COSName.get_pdf_name("BaseEncoding"),
        COSName.get_pdf_name("WinAnsiEncoding"),
    )
    diffs = COSArray()
    diffs.add(COSInteger.get(0x41))
    diffs.add(COSName.get_pdf_name("Aacute"))
    font_enc.set_item(COSName.get_pdf_name("Differences"), diffs)

    enc = DictionaryEncoding(font_encoding=font_enc, is_non_symbolic=True)
    # Differences override WinAnsi at 0x41.
    assert enc.get_name(0x41) == "Aacute"
    # Base flows through everywhere else.
    assert enc.get_name(0x20) == "space"


def test_type3_font_has_no_implicit_base() -> None:
    # Type 3 fonts (font_encoding without is_non_symbolic/built_in arguments)
    # carry no implicit base — /Differences is the complete mapping.
    font_enc = COSDictionary()
    font_enc.set_item(COSName.TYPE, COSName.get_pdf_name("Encoding"))
    diffs = COSArray()
    diffs.add(COSInteger.get(0x20))
    diffs.add(COSName.get_pdf_name("space"))
    diffs.add(COSName.get_pdf_name("a"))
    font_enc.set_item(COSName.get_pdf_name("Differences"), diffs)

    enc = DictionaryEncoding(font_encoding=font_enc)
    assert enc.is_type3() is True
    assert enc.get_base_encoding() is None
    assert enc.get_name(0x20) == "space"
    assert enc.get_name(0x21) == "a"
    # Codes outside /Differences are .notdef — no base to fall through to.
    assert enc.get_name(0x41) == ".notdef"


def test_unknown_base_encoding_name_falls_through_to_default() -> None:
    # When /BaseEncoding is a name not in the predefined set, the resolved
    # base encoding is None; the non-symbolic/symbolic default takes over.
    font_enc = COSDictionary()
    font_enc.set_item(COSName.TYPE, COSName.get_pdf_name("Encoding"))
    font_enc.set_item(
        COSName.get_pdf_name("BaseEncoding"),
        COSName.get_pdf_name("NotARealEncoding"),
    )
    enc = DictionaryEncoding(font_encoding=font_enc, is_non_symbolic=True)
    # Falls through to StandardEncoding (non-symbolic default).
    assert enc.get_base_encoding() is StandardEncoding.INSTANCE


def test_type1_encoding_from_font_box_copy() -> None:
    # Type1Encoding.from_font_box copies the FontBox-level encoding's
    # code-to-name map into a fresh Type1Encoding.
    class _FakeFontBoxEncoding:
        def get_code_to_name_map(self) -> dict[int, str]:
            return {0x41: "A", 0x42: "B", 0x43: "C"}

    enc = Type1Encoding.from_font_box(_FakeFontBoxEncoding())
    assert enc.get_name(0x41) == "A"
    assert enc.get_code("C") == 0x43
    assert enc.get_encoding_name() == "built-in (Type 1)"
    # Type 1 encodings have no COS representation.
    assert enc.get_cos_object() is None


def test_type1_encoding_no_args_constructor_is_empty() -> None:
    enc = Type1Encoding()
    assert enc.size() == 0
    assert enc.get_name(0x41) == ".notdef"


def test_dictionary_encoding_layered_on_type1_built_in() -> None:
    # End-to-end: a Type 1 font with a built-in encoding (Type1Encoding)
    # layered under a DictionaryEncoding /Differences overlay.
    type1 = Type1Encoding()
    type1.add(0x41, "A_t1")
    type1.add(0x42, "B_t1")
    type1.add(0x80, "highbit_t1")

    font_enc = COSDictionary()
    font_enc.set_item(COSName.TYPE, COSName.get_pdf_name("Encoding"))
    diffs = COSArray()
    diffs.add(COSInteger.get(0x41))
    diffs.add(COSName.get_pdf_name("A_override"))
    font_enc.set_item(COSName.get_pdf_name("Differences"), diffs)

    enc = DictionaryEncoding(
        font_encoding=font_enc, is_non_symbolic=False, built_in=type1
    )
    # 0x41 overridden by differences.
    assert enc.get_name(0x41) == "A_override"
    # 0x42 + 0x80 still flow from the Type1 built-in.
    assert enc.get_name(0x42) == "B_t1"
    assert enc.get_name(0x80) == "highbit_t1"
