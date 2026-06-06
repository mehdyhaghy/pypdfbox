"""Edge-case behavioural tests for JBIG2Document stream mapping.

Covers the file-header / organisation branches not exercised by the real
``.jb2`` corpus fixtures (which are all sequential, known-page-count, no
extended template, and always start at page 1):

* the standalone file header with the extended-template flag set;
* the standalone file header with a *known* page count (D.4.3 number-of-pages
  field, header length 13);
* the random-access organisation, where data offsets are assigned after all
  segment headers are mapped (``_determine_random_data_offsets``);
* the PDFBOX-6147 "page 1 missing" abort;
* re-mapping a globals-only stream via ``get_amount_of_pages``.

These use minimal hand-built JBIG2 streams: file-header magic + flag byte
(+ optional 4-byte page count) + minimal segment headers (segment number,
flags, zero referred-to segments, page-association byte, 4-byte data length).
"""

from __future__ import annotations

import struct
from pathlib import Path

import pytest

from pypdfbox.jbig2.io.image_input_stream import ImageInputStream
from pypdfbox.jbig2.jbig2_document import JBIG2Document

_MAGIC = bytes((0x97, 0x4A, 0x42, 0x32, 0x0D, 0x0A, 0x1A, 0x0A))
_FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _doc(data: bytes) -> JBIG2Document:
    return JBIG2Document(ImageInputStream(data))


def _segment(nr: int, seg_type: int, page_assoc: int, data_len: int = 0) -> bytes:
    # 7.2.2 segment number (4 bytes), 7.2.3 flag byte
    # (retain=0, page-assoc-size=0 -> short, type in low 6 bits),
    # 7.2.4 rts byte (count=0, short format), 7.2.6 page assoc (1 byte short),
    # 7.2.7 data length (4 bytes).
    flag = seg_type & 0x3F
    return (
        struct.pack(">I", nr)
        + bytes((flag, 0x00, page_assoc & 0xFF))
        + struct.pack(">I", data_len)
    )


def test_extended_template_flag_parsed():
    # flag byte: bit2 ext-template=1, bit1 pages-unknown=1, bit0 org=1 (seq).
    data = _MAGIC + bytes((0b00000111,))
    doc = _doc(data)
    assert doc.is_gb_use_ext_template() is True
    assert doc.is_amount_of_pages_unknown() is True
    assert doc.file_header_length == 9


def test_known_page_count_header_length_13():
    # bit1 pages-unknown=0 -> number-of-pages field present (D.4.3).
    data = _MAGIC + bytes((0b00000001,)) + struct.pack(">I", 7)
    doc = _doc(data)
    assert doc.is_amount_of_pages_unknown() is False
    assert doc.amount_of_pages == 7
    assert doc.file_header_length == 13
    # amount-of-pages takes the "known" branch and returns the declared count.
    assert doc.get_amount_of_pages() == 7


def test_random_organisation_assigns_data_offsets():
    # bit0 org=0 (random); one EOF segment (type 51) with page association 0
    # (global) and a non-zero data length so the offset advances.
    data = _MAGIC + bytes((0b00000010,)) + _segment(0, 51, 0, data_len=5)
    doc = _doc(data)
    assert doc.organisation_type == JBIG2Document.RANDOM
    seg = doc.get_global_segment(0)
    assert seg is not None
    assert seg.get_segment_type() == 51
    # Random data starts after the segment header (offset assigned by
    # _determine_random_data_offsets), not during header parsing.
    assert seg.get_segment_data_start_offset() == len(data)


def test_page_one_missing_raises():
    # Sequential, a single page-information segment associated with page 2.
    data = _MAGIC + bytes((0b00000011,)) + _segment(0, 48, page_assoc=2)
    with pytest.raises(OSError, match="Page 1 missing"):
        _doc(data)


def test_globals_only_stream_remaps_on_amount_of_pages():
    # 21.glob is the real embedded globals-only stream: no file header, only a
    # symbol dictionary, no page. amount-of-pages stays unknown, so the first
    # get_amount_of_pages re-runs _map_stream (pages empty) and reports zero.
    doc = JBIG2Document(ImageInputStream((_FIXTURES / "21.glob").read_bytes()))
    assert not doc.pages
    assert doc.is_amount_of_pages_unknown() is True
    assert doc.get_amount_of_pages() == 0


def test_no_file_header_embedded_stream_starts_at_offset_zero():
    # No magic -> embedded organisation, sequential default. A single page-1
    # page-information segment maps cleanly.
    data = _segment(0, 48, page_assoc=1)
    doc = JBIG2Document(ImageInputStream(data))
    assert doc.file_header_length == 9
    assert doc.get_page(1) is not None
