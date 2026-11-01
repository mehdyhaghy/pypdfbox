"""``PDType1Font(Standard14Fonts.FontName)``: the upstream Standard 14
constructor (``new PDType1Font(Standard14Fonts.FontName.HELVETICA)``)."""

import io

import pytest

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdfwriter.compress.compress_parameters import CompressParameters
from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.pdmodel.font import PDType1Font
from pypdfbox.pdmodel.font.encoding.symbol_encoding import SymbolEncoding
from pypdfbox.pdmodel.font.encoding.win_ansi_encoding import WinAnsiEncoding
from pypdfbox.pdmodel.font.encoding.zapf_dingbats_encoding import (
    ZapfDingbatsEncoding,
)
from pypdfbox.pdmodel.font.pd_font_factory import PDFontFactory
from pypdfbox.pdmodel.font.standard14_fonts import Standard14Fonts
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream
from tests.oracle.harness import requires_oracle, run_probe_text

FontName = Standard14Fonts.FontName

_LATIN = [
    " ", "Hello, World!", "0123456789", "(a) \\ [b] {c}", "éèüñçÿ",
    "€•—™", "fi fl", "α",
]
_SYMBOL = [" ", "ΑΒΓαβγ", "∑∞≠", "(1+2)=3", "A"]
_DINGBATS = [" ", "✁✂✃", "❤➡", "●", "A"]


def _entries(font: PDType1Font) -> list[tuple[str, str]]:
    return [(k.name, str(v)) for k, v in font.get_cos_object().entry_set()]


@pytest.mark.parametrize("name", list(FontName), ids=lambda n: n.name)
def test_dictionary_matches_upstream_shape(name: FontName) -> None:
    font = PDType1Font(name)
    expected = [("Type", "/Font"), ("Subtype", "/Type1"), ("BaseFont", f"/{name.value}")]
    if name not in (FontName.SYMBOL, FontName.ZAPF_DINGBATS):
        expected.append(("Encoding", "/WinAnsiEncoding"))
    assert _entries(font) == expected
    assert font.get_name() == name.value
    assert font.is_standard14()
    assert not font.is_embedded()


def test_encoding_selection() -> None:
    assert isinstance(PDType1Font(FontName.HELVETICA).get_encoding_typed(), WinAnsiEncoding)
    assert PDType1Font(FontName.SYMBOL).get_encoding_typed() is SymbolEncoding.INSTANCE
    assert (
        PDType1Font(FontName.ZAPF_DINGBATS).get_encoding_typed()
        is ZapfDingbatsEncoding.INSTANCE
    )


def test_widths_and_encode_use_afm() -> None:
    font = PDType1Font(FontName.HELVETICA)
    assert font.encode("Hello") == b"Hello"
    # Helvetica AFM: H=722 e=556 l=222 l=222 o=556.
    assert font.get_string_width("Hello") == 2278.0
    assert font.get_width(0x80) == 556.0  # WinAnsi 0x80 = Euro


def test_standard14_classmethod_and_factory_build_same_dict() -> None:
    direct = PDType1Font(FontName.TIMES_BOLD)
    assert _entries(PDType1Font.standard14("Times-Bold")) == _entries(direct)
    assert _entries(PDFontFactory.create_default_font("Times-Bold")) == _entries(direct)


def test_standard14_classmethod_keeps_non_standard_names() -> None:
    font = PDType1Font.standard14("NotAStandardFont")
    assert font.get_name() == "NotAStandardFont"
    assert font.get_sub_type() == "Type1"


def test_dictionary_constructor_still_works() -> None:
    d = COSDictionary()
    d.set_name(COSName.get_pdf_name("BaseFont"), "Courier")
    font = PDType1Font(d)
    assert font.get_cos_object() is d
    assert font.get_name() == "Courier"
    assert PDType1Font().get_sub_type() == "Type1"


def test_font_usable_on_a_page() -> None:
    with PDDocument() as doc:
        page = PDPage()
        doc.add_page(page)
        with PDPageContentStream(doc, page) as cs:
            cs.begin_text()
            cs.set_font(PDType1Font(FontName.HELVETICA), 12)
            cs.show_text("Hello (world)")
            cs.end_text()
        buf = io.BytesIO()
        doc.save(buf, CompressParameters.NO_COMPRESSION)
    assert b"/BaseFont /Helvetica" in buf.getvalue()


def _python_lines() -> list[str]:
    lines: list[str] = []
    for name in FontName:
        font = PDType1Font(name)
        lines.append(f"FONT\t{name.name}")
        lines.extend(f"D\t{k}\t{v}" for k, v in _entries(font))
        lines.append(f"ENC\t{type(font.get_encoding_typed()).__name__}")
        lines.extend(f"W\t{code}\t{font.get_width(code):.4f}" for code in range(256))
        samples = (
            _SYMBOL if name is FontName.SYMBOL
            else _DINGBATS if name is FontName.ZAPF_DINGBATS
            else _LATIN
        )
        for i, sample in enumerate(samples):
            lines.append(f"E\t{i}\t{font.encode(sample).hex().upper()}")
            lines.append(f"SW\t{i}\t{font.get_string_width(sample):.4f}")
    return lines


@requires_oracle
def test_matches_pdfbox_for_all_14_fonts() -> None:
    java = run_probe_text("Std14CtorProbe").splitlines()
    python = _python_lines()
    assert len(java) == len(python)
    for j, p in zip(java, python, strict=True):
        if j.endswith("\tERR"):
            # Upstream throws for an unencodable character; pypdfbox's simple
            # fonts substitute ``?`` instead (documented in CHANGES.md).
            assert j.split("\t")[:2] == p.split("\t")[:2]
            continue
        assert p == j
