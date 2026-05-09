from __future__ import annotations

import io
import logging

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSObject, COSStream
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.multipdf import PDFCloneUtility, PDFMergerUtility
from pypdfbox.pdfparser import BaseParser, PDFParseError
from pypdfbox.pdfparser.pdf_stream_parser import PDFStreamParser
from pypdfbox.pdmodel import PDDocument


def base_parser(data: bytes) -> BaseParser:
    return BaseParser(RandomAccessReadBuffer(data))


def stream_parser(data: bytes) -> PDFStreamParser:
    return PDFStreamParser(RandomAccessReadBuffer(data))


def test_require_byte_returns_byte_before_eof() -> None:
    parser = base_parser(b"x")

    assert parser.require_byte() == ord("x")


def test_read_name_falls_back_to_latin1_for_invalid_utf8_escape() -> None:
    assert base_parser(b"/bad#FFname").read_name() == "bad\xffname"


def test_literal_string_inner_close_near_eof_keeps_depth_then_raises() -> None:
    with pytest.raises(PDFParseError, match="unterminated"):
        base_parser(b"((x)").read_literal_string()


def test_literal_string_trailing_backslash_hits_escape_eof_then_raises() -> None:
    with pytest.raises(PDFParseError, match="unterminated"):
        base_parser(b"(abc\\").read_literal_string()


class _FalseEofBuffer(RandomAccessReadBuffer):
    def is_eof(self) -> bool:
        return False


def test_stream_parser_returns_none_when_peek_reports_eof() -> None:
    parser = PDFStreamParser(_FalseEofBuffer(b""))

    assert parser.parse_next_token() is None


def test_inline_image_data_reader_breaks_when_first_byte_is_eof() -> None:
    parser = stream_parser(b"ID")

    op = parser.parse_next_token()

    assert op is not None
    assert op.get_name() == "ID"
    assert op.get_image_data() == b""


def test_has_no_following_bin_data_accepts_empty_probe_at_eof() -> None:
    parser = stream_parser(b"")

    assert parser._has_no_following_bin_data() is True


def test_has_no_following_bin_data_rejects_non_operator_ascii_probe() -> None:
    parser = stream_parser(b" abc ")

    assert parser._has_no_following_bin_data() is False


def test_clone_unresolved_cos_object_returns_none() -> None:
    with PDDocument() as destination:
        cloner = PDFCloneUtility(destination)

        assert cloner.clone_for_new_document(COSObject(1, 0)) is None


def test_clone_array_self_reference_uses_new_array() -> None:
    with PDDocument() as destination:
        cloner = PDFCloneUtility(destination)
        array = COSArray()
        array.add(COSObject(2, 0, resolved=array))

        cloned = cloner.clone_for_new_document(array)

        assert isinstance(cloned, COSArray)
        assert cloned.get(0) is cloned


def test_clone_stream_self_reference_uses_new_stream() -> None:
    with PDDocument() as destination:
        cloner = PDFCloneUtility(destination)
        stream = COSStream()
        stream.set_item("Self", COSObject(3, 0, resolved=stream))

        cloned = cloner.clone_for_new_document(stream)

        assert isinstance(cloned, COSStream)
        assert cloned.get_item("Self") is cloned


def test_clone_merge_none_base_is_noop() -> None:
    with PDDocument() as destination:
        cloner = PDFCloneUtility(destination)
        target = COSArray([COSInteger.get(1)])

        cloner.clone_merge(None, object())

        assert target.size() == 1


def test_clone_merge_unresolved_source_reference_is_noop() -> None:
    with PDDocument() as destination:
        cloner = PDFCloneUtility(destination)
        target = COSDictionary()

        cloner._clone_merge_cos_base(COSObject(4, 0), target, set())

        assert target.is_empty()


def test_merger_final_cleanup_logs_source_close_failure(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    class BadSource:
        def __init__(self) -> None:
            self.close_calls = 0

        def close(self) -> None:
            self.close_calls += 1
            if self.close_calls == 1:
                raise SystemExit("first close aborts immediate cleanup")
            raise OSError("cannot close source")

    util = PDFMergerUtility()
    util.add_source(b"%PDF-placeholder")
    util.set_destination_stream(io.BytesIO())
    bad_source = BadSource()

    monkeypatch.setattr(
        PDFMergerUtility,
        "_open_source",
        staticmethod(lambda source: (bad_source, True)),
    )
    monkeypatch.setattr(PDFMergerUtility, "append_document", lambda *args: None)

    with (
        caplog.at_level(logging.ERROR, logger="pypdfbox.multipdf.pdf_merger_utility"),
        pytest.raises(SystemExit, match="first close"),
    ):
        util.merge_documents()

    messages = [record.getMessage() for record in caplog.records]
    assert messages.count("error closing source PDDocument") == 1
