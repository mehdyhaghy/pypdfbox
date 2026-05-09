from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSInteger,
    COSName,
    COSObject,
    COSObjectKey,
)
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import COSParser


def _parser(data: bytes) -> COSParser:
    return COSParser(RandomAccessReadBuffer(data))


def test_wave643_header_predicates_preserve_position_and_default_versions() -> None:
    parser = _parser(b"garbage\n%PDF-\n%FDF-\n")
    parser.seek(3)

    assert parser.has_pdf_header()
    assert parser.position == 3
    assert parser.parse_pdf_header() == 1.4

    parser.seek(5)
    assert parser.has_fdf_header()
    assert parser.position == 5
    assert parser.parse_fdf_header() == 1.0


def test_wave643_set_lenient_rejects_changes_after_initial_parse_latch() -> None:
    parser = _parser(b"")
    parser.set_lenient(False)
    parser.set_initial_parse_done(True)

    with pytest.raises(ValueError, match="Cannot change leniency"):
        parser.set_lenient(True)

    assert not parser.is_lenient()


def test_wave643_rebuild_trailer_recovers_root_info_encrypt_id_and_size() -> None:
    data = (
        b"1 0 obj\n<< /Type /Catalog >>\nendobj\n"
        b"2 0 obj\n<< /Producer (pypdfbox) >>\nendobj\n"
        b"4 0 obj\n<< /Encrypt << /Filter /Standard >> "
        b"/ID [<00112233> <44556677>] >>\nendobj\n"
    )
    trailer = _parser(data).rebuild_trailer()

    root = trailer.get_item(COSName.ROOT)
    info = trailer.get_item(COSName.INFO)
    encrypt = trailer.get_dictionary_object(COSName.ENCRYPT)
    ids = trailer.get_dictionary_object("ID")

    assert isinstance(root, COSObject)
    assert root.get_object_number() == 1
    assert isinstance(info, COSObject)
    assert info.get_object_number() == 2
    assert isinstance(encrypt, COSDictionary)
    assert encrypt.get_name("Filter") == "Standard"
    assert isinstance(ids, COSArray)
    assert ids.size() == 2
    assert trailer.get_int("Size") == 5


def test_wave643_parse_xref_stream_treats_float_widths_as_integer_widths() -> None:
    xref = COSDictionary()
    widths = COSArray()
    widths.add(COSInteger.get(1))
    widths.add(_parser(b"2.7").parse_cos_number())
    xref.set_item("W", widths)
    xref.set_item("Size", COSInteger.get(2))

    table = _parser(b"").parse_xref_stream(xref)

    assert table == {
        COSObjectKey(0, 0): 0,
        COSObjectKey(1, 0): 3,
    }
