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


def test_equals_mirrors_arrays_equals() -> None:
    # COSName.java:823-827: equality is Arrays.equals(nameBytes, ...).
    # Two distinct interns of the same parsed bytes must compare equal.
    a = _name_from_bytes(b"/Type")
    b = COSName.get_pdf_name("Type")
    assert a.equals(b) is True
    assert COSName.get_pdf_name("Pages").equals(b) is False
    # Anything that isn't a COSName never equals (Java's instanceof guard).
    assert a.equals("Type") is False


def test_hash_code_mirrors_arrays_hash_code() -> None:
    # COSName.java:829-833 uses Arrays.hashCode(byte[]).
    # The recipe: int h = 1; for (byte b : nameBytes) h = 31 * h + b;
    # with `b` widened as signed int. Verified against a few short names.
    assert COSName.get_pdf_name(b"").hash_code() == 1
    assert COSName.get_pdf_name("A").hash_code() == 96
    assert COSName.get_pdf_name("AB").hash_code() == 3042
    # Equal names produce equal hashes.
    assert (
        COSName.get_pdf_name("Type").hash_code()
        == COSName.get_pdf_name("Type").hash_code()
    )


def test_to_string_uses_cosname_braces() -> None:
    # COSName.java:817-821: toString() returns "COSName{" + getName() + "}".
    assert COSName.get_pdf_name("Type").to_string() == "COSName{Type}"
    assert COSName.get_pdf_name("").to_string() == "COSName{}"
    # Round-tripped via getName(), so unicode names appear decoded.
    assert COSName.get_pdf_name("中").to_string() == "COSName{中}"
