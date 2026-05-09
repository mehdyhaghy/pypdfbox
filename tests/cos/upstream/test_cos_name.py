"""
Ported from Apache PDFBox 3.0:
  pdfbox/src/test/java/org/apache/pdfbox/cos/TestCOSName.java

The upstream tests exercise the behavior through full document load/save
fixtures. The parity assertions here pin the same COSName contracts directly:
Unicode names survive dictionary storage, and parsed raw name bytes are
written back with PDFBox's ``#XX`` escaping rules.
"""

from __future__ import annotations

import io

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import COSParser
from pypdfbox.pdfwriter.cos_writer import COSWriter


def _name_from_bytes(data: bytes) -> COSName:
    parser = COSParser(RandomAccessReadBuffer(data))
    return parser.parse_cos_name()


def _write_name(name: COSName) -> str:
    out = io.BytesIO()
    name.write_pdf(out)
    return out.getvalue().decode("ascii")


def test_pdfbox4076() -> None:
    special = "中国你好!"
    dictionary = COSDictionary()
    out = io.BytesIO()

    dictionary.set_string(COSName.get_pdf_name(special), special)
    COSName.get_pdf_name(special).write_pdf(out)

    assert dictionary.contains_key(special)
    assert dictionary.get_string(special) == special
    assert out.getvalue() == (
        b"/#E4#B8#AD#E5#9B#BD#E4#BD#A0#E5#A5#BD#21"
    )


def test_pdfbox6178() -> None:
    name = _name_from_bytes(b"/m#E4nnlich")

    assert name.get_bytes() == b"m\xe4nnlich"
    assert name.get_name() == "m\xe4nnlich"
    assert _write_name(name) == "/m#E4nnlich"


def test_name_with_ascii_nul() -> None:
    name = _name_from_bytes(b"/m#00nnlich")

    assert name.get_bytes() == b"m\x00nnlich"
    assert _write_name(name) == "/m#00nnlich"


def test_raw_name_bytes_do_not_collide_with_utf8_text() -> None:
    raw = _name_from_bytes(b"/#E4")
    text = COSName.get_pdf_name("ä")

    assert raw != text
    assert raw.get_bytes() == b"\xe4"
    assert text.get_bytes() == b"\xc3\xa4"
    assert _write_name(raw) == "/#E4"
    assert _write_name(text) == "/#C3#A4"


def test_dictionary_key_preserves_raw_name_bytes_when_written() -> None:
    parser = COSParser(RandomAccessReadBuffer(b"<< /m#E4nnlich true >>"))
    dictionary = parser.parse_cos_dictionary()
    out = io.BytesIO()

    COSWriter(out).visit_from_dictionary(dictionary)

    assert b"/m#E4nnlich" in out.getvalue()
    assert b"/m#C3#A4nnlich" not in out.getvalue()
