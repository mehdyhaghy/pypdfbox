from __future__ import annotations

import pytest

from pypdfbox.cos import COSName, COSObjectKey
from pypdfbox.filter import FilterFactory
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import BaseParser
from pypdfbox.pdfwriter.cos_writer_xref_entry import COSWriterXRefEntry


def _parser(data: bytes) -> BaseParser:
    return BaseParser(RandomAccessReadBuffer(data))


def test_wave846_parser_upstream_aliases_rewind_without_using_byte_value() -> None:
    parser = _parser(b"ab")

    parser.unread(255)
    assert parser.read() == ord("a")

    parser.unread(0)
    assert parser.peek() == ord("a")
    assert parser.read_byte() == ord("a")


def test_wave846_parser_name_terminators_include_eof_and_form_feed() -> None:
    assert BaseParser.is_end_of_name(-1) is True
    assert BaseParser.is_end_of_name(0x0C) is True
    assert BaseParser.is_regular(-1) is False


def test_wave846_filter_factory_instance_resolves_cosname_short_name() -> None:
    long_filter = FilterFactory.INSTANCE.get_filter(COSName.FLATE_DECODE)

    assert (
        FilterFactory.INSTANCE.get_filter_by_short_name(COSName.get_pdf_name("Fl"))
        is long_filter
    )
    assert FilterFactory.INSTANCE.is_registered(COSName.get_pdf_name("Fl")) is True


def test_wave846_filter_factory_rejects_unknown_short_name() -> None:
    with pytest.raises(KeyError, match="unknown filter short name"):
        FilterFactory.INSTANCE.get_filter_by_short_name(COSName.get_pdf_name("ZZ"))


def test_wave846_xref_entry_le_ge_compare_by_object_number_only() -> None:
    entry = COSWriterXRefEntry(offset=99, key=COSObjectKey(3, 7), free=True)
    same_object = COSWriterXRefEntry(offset=1, key=COSObjectKey(3, 0))
    later = COSWriterXRefEntry(offset=0, key=COSObjectKey(5, 0))

    assert entry <= same_object
    assert entry >= same_object
    assert entry <= later
    assert later >= entry
