from __future__ import annotations

import pytest

from pypdfbox.cos import COSDocument, COSInteger, COSName, COSObjectKey, COSStream
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import COSParser, PDFParseError


def _parser(data: bytes, document: COSDocument | None = None) -> COSParser:
    return COSParser(RandomAccessReadBuffer(data), document=document)


def test_wave623_missing_eol_after_stream_keyword_rewinds_body_byte() -> None:
    parser = _parser(b"ABCDE")

    parser._consume_eol_after_stream_keyword()  # noqa: SLF001

    assert parser.position == 0
    assert parser.peek() == ord("A")


def test_wave623_stream_keyword_requires_dictionary_body() -> None:
    parser = _parser(b"7 0 obj 42 stream\nABCDE\nendstream endobj")

    with pytest.raises(PDFParseError, match="not a dictionary"):
        parser.parse_indirect_object_definition()


def test_wave623_xref_object_stream_can_return_dictionary_without_body() -> None:
    stream = _parser(
        b"9 0 obj << /Type /XRef /Length 0 /Size 1 /W [1 1 1] >> endobj"
    ).parse_xref_object_stream(0)

    assert isinstance(stream, COSStream)
    assert stream.get_name("Type") == "XRef"
    assert not stream.is_skip_encryption()


def test_wave623_xref_object_stream_rejects_non_dictionary_body() -> None:
    parser = _parser(b"9 0 obj 42 endobj")

    with pytest.raises(PDFParseError, match="body is not a dictionary"):
        parser.parse_xref_object_stream(0)


def test_wave623_parse_object_stream_rejects_bad_metadata_shapes() -> None:
    doc = COSDocument()
    try:
        bad_stream = COSStream()
        # Wave 1516: ``/Type`` is no longer validated (upstream
        # ``PDFObjectStreamParser`` checks only ``/N`` and ``/First``), so a
        # non-``/ObjStm`` container with NO ``/N`` surfaces the "missing /N"
        # error instead of a "/Type" error — the bad-metadata rejection still
        # holds, just at the field upstream actually inspects.
        bad_stream.set_item(COSName.TYPE, COSName.get_pdf_name("NotObjStm"))
        doc.get_object_from_pool(COSObjectKey(5, 0)).set_object(bad_stream)

        with pytest.raises(PDFParseError, match="/N entry missing"):
            _parser(b"", document=doc).parse_object_stream(5)
    finally:
        doc.close()


def test_wave623_parse_object_stream_tolerates_inflated_n() -> None:
    # Wave 1503: upstream ``PDFObjectStreamParser`` reads at most /N pairs but
    # stops at the /First boundary, so an /N larger than the actual header pair
    # count (here /N=2 with a single ``10 0`` pair) no longer raises "header
    # truncated" — the lone member parses. The header region is ``decoded[:5]``
    # = ``"10 0 "`` and the payload at /First is ``42``.
    doc = COSDocument()
    try:
        obj_stream = COSStream()
        obj_stream.set_item(COSName.TYPE, COSName.get_pdf_name("ObjStm"))
        obj_stream.set_item(COSName.get_pdf_name("N"), COSInteger.get(2))
        obj_stream.set_item(COSName.get_pdf_name("First"), COSInteger.get(5))
        obj_stream.set_raw_data(b"10 0 42")
        doc.get_object_from_pool(COSObjectKey(5, 0)).set_object(obj_stream)

        parsed = _parser(b"", document=doc).parse_object_stream(5)
        assert parsed == [COSInteger.get(42)]
        assert doc.has_object(COSObjectKey(10, 0))
    finally:
        doc.close()
