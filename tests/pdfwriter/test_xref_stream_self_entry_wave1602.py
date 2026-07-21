"""PDFBOX-6176 (upstream 3.0.8): the incremental-save xref STREAM lists
ITSELF in its own cross-reference data.

Upstream ``COSWriter.doWriteXRefInc`` (fix commit c827ba96) pre-assigns the
xref stream's object key (``++number``), feeds its OWN ``NormalXReference``
(type-1 row at the stream's byte offset) into ``PDFXRefStream`` BEFORE
``getStream()`` serialises the body, and sets ``/Size = number + 1``. As a
result the appended xref stream's ``/Index`` covers its own object number,
the stream data carries a row for it at the correct byte offset, and no xref
gap is left at the stream's own number. PDFBox 3.0.7 registered the
self-entry only after serialisation, so 3.0.7 output omits it — pypdfbox
followed that bug for oracle parity until wave 1602.

NOTE: the live oracle jars under ``archive/oracle/`` are still 3.0.7, so
differential probes show the OLD (self-entry-less) output until the jars are
swapped. These tests are therefore oracle-free pins of the 3.0.8 shape,
asserted directly against the Java source of ``COSWriter.doWriteXRefInc`` /
``PDFXRefStream`` at 3.0.8.
"""

from __future__ import annotations

import io
import re
import zlib
from pathlib import Path

from pypdfbox.loader import Loader
from pypdfbox.pdmodel import PDDocument
from pypdfbox.pdmodel.common import PDRectangle

_XREF_STREAM_FIXTURE = (
    Path(__file__).resolve().parents[1] / "fixtures" / "pdfwriter" / "unencrypted.pdf"
)


def _source_bytes() -> bytes:
    return _XREF_STREAM_FIXTURE.read_bytes()


def _save_incremental_with_page_edit(src: bytes) -> bytes:
    doc = PDDocument(Loader.load_pdf(src))
    try:
        page = doc.get_page(0)
        page.set_media_box(PDRectangle(0, 0, 333, 444))
        page.get_cos_object().set_needs_to_be_updated(True)
        sink = io.BytesIO()
        doc.save_incremental(sink)
    finally:
        doc.close()
    return sink.getvalue()


def _appended_xref_stream(out: bytes, src: bytes) -> tuple[int, int, dict[str, bytes], bytes]:
    """Parse the appended ``/Type /XRef`` object out of the increment tail.

    Returns ``(own_number, absolute_offset_of_obj_frame, dict_fields, data)``
    where ``dict_fields`` maps ``Index`` / ``W`` / ``Size`` / ``Prev`` to the
    raw value bytes and ``data`` is the inflated stream body.
    """
    assert out.startswith(src)
    tail = out[len(src) :]
    type_at = tail.find(b"/Type /XRef")
    if type_at == -1:
        type_at = tail.find(b"/Type/XRef")
    assert type_at != -1, "no appended /Type /XRef stream"
    frames = list(re.finditer(rb"(\d+)\s+(\d+)\s+obj\b", tail[:type_at]))
    assert frames, "no obj frame precedes /Type /XRef"
    frame = frames[-1]
    own_number = int(frame.group(1))
    own_offset = len(src) + frame.start()

    dict_body = tail[frame.end() : tail.find(b"stream", type_at)]
    fields: dict[str, bytes] = {}
    for name, pattern in (
        ("Index", rb"/Index\s*\[([^\]]*)\]"),
        ("W", rb"/W\s*\[([^\]]*)\]"),
        ("Size", rb"/Size\s+(\d+)"),
        ("Prev", rb"/Prev\s+(\d+)"),
    ):
        m = re.search(pattern, dict_body)
        assert m is not None, f"/{name} missing from appended xref stream dict"
        fields[name] = m.group(1)

    stream_kw = tail.find(b"stream", type_at)
    data_start = stream_kw + len(b"stream")
    if tail[data_start : data_start + 2] == b"\r\n":
        data_start += 2
    elif tail[data_start : data_start + 1] == b"\n":
        data_start += 1
    data_end = tail.find(b"endstream", data_start)
    assert data_end != -1
    raw = tail[data_start:data_end]
    return own_number, own_offset, fields, zlib.decompress(raw)


def _rows(data: bytes, widths: list[int]) -> list[tuple[int, ...]]:
    stride = sum(widths)
    assert stride > 0 and len(data) % stride == 0, (widths, len(data))
    rows: list[tuple[int, ...]] = []
    for off in range(0, len(data), stride):
        row: list[int] = []
        pos = off
        for w in widths:
            row.append(int.from_bytes(data[pos : pos + w], "big") if w else 0)
            pos += w
        rows.append(tuple(row))
    return rows


def _index_numbers(index_field: bytes) -> list[int]:
    ints = [int(x) for x in index_field.split()]
    nums: list[int] = []
    for i in range(0, len(ints) - 1, 2):
        nums.extend(range(ints[i], ints[i] + ints[i + 1]))
    return nums


def test_self_entry_present_at_correct_offset() -> None:
    """The appended xref stream carries a type-1 row for its OWN object
    number pointing at its own ``N 0 obj`` byte offset (PDFBOX-6176)."""
    src = _source_bytes()
    out = _save_incremental_with_page_edit(src)
    own_number, own_offset, fields, data = _appended_xref_stream(out, src)

    widths = [int(x) for x in fields["W"].split()]
    assert len(widths) == 3
    index_numbers = _index_numbers(fields["Index"])
    rows = _rows(data, widths)
    # The stream body is the object-0 free-head row followed by the sorted
    # streamData rows — exactly one row per /Index-covered number.
    assert len(rows) == len(index_numbers)

    row_by_number = dict(zip(index_numbers, rows, strict=True))
    assert own_number in row_by_number, "/Index must cover the stream's own number"
    self_row = row_by_number[own_number]
    assert self_row[0] == 1, "self-entry must be a type-1 (uncompressed) row"
    assert self_row[1] == own_offset, "self-entry offset must be the stream's own"
    assert self_row[2] == 0, "self-entry generation must be 0"

    # startxref agrees with the self-entry's offset.
    startxref = int(re.findall(rb"startxref\s+(\d+)", out)[-1])
    assert startxref == own_offset


def test_index_covers_free_head_page_and_self() -> None:
    """/Index = object 0 (free head) + the rewritten page + the stream
    itself, nothing else, for a single-page MediaBox edit."""
    src = _source_bytes()
    doc = PDDocument(Loader.load_pdf(src))
    try:
        page = doc.get_page(0)
        page_num = doc.get_document().get_key(page.get_cos_object()).object_number
        page.set_media_box(PDRectangle(0, 0, 333, 444))
        page.get_cos_object().set_needs_to_be_updated(True)
        sink = io.BytesIO()
        doc.save_incremental(sink)
    finally:
        doc.close()
    out = sink.getvalue()

    own_number, _own_offset, fields, _data = _appended_xref_stream(out, src)
    assert sorted(_index_numbers(fields["Index"])) == sorted(
        {0, page_num, own_number}
    )


def test_size_is_own_number_plus_one() -> None:
    """/Size mirrors upstream ``setSize(number + 1)`` where ``number`` is the
    pre-incremented xref stream object number — i.e. one greater than the
    highest object number in the file, including the stream itself
    (PDF 32000-1 section 7.5.8)."""
    src = _source_bytes()
    out = _save_incremental_with_page_edit(src)
    own_number, _own_offset, fields, _data = _appended_xref_stream(out, src)
    assert int(fields["Size"]) == own_number + 1
    # The stream is a brand-new number above every source object.
    src_doc = Loader.load_pdf(src)
    try:
        source_max = max(k.object_number for k in src_doc.get_object_keys())
    finally:
        src_doc.close()
    assert own_number > source_max


def test_round_trip_reparses_cleanly() -> None:
    """load -> save_incremental -> reload: the appended revision parses, the
    edit survives, and the xref stream object itself resolves through the
    cross-reference (no gap at its own number)."""
    src = _source_bytes()
    out = _save_incremental_with_page_edit(src)

    reloaded = PDDocument(Loader.load_pdf(out))
    try:
        mb = reloaded.get_page(0).get_media_box()
        assert (mb.get_width(), mb.get_height()) == (333.0, 444.0)
    finally:
        reloaded.close()


def test_second_increment_chains_over_self_listed_stream() -> None:
    """A second save_incremental over the first increment's output works:
    the second stream's /Prev points at the first stream's offset and both
    revisions stay parseable."""
    src = _source_bytes()
    first = _save_incremental_with_page_edit(src)
    first_startxref = int(re.findall(rb"startxref\s+(\d+)", first)[-1])

    doc = PDDocument(Loader.load_pdf(first))
    try:
        page = doc.get_page(0)
        page.set_media_box(PDRectangle(0, 0, 555, 666))
        page.get_cos_object().set_needs_to_be_updated(True)
        sink = io.BytesIO()
        doc.save_incremental(sink)
    finally:
        doc.close()
    second = sink.getvalue()

    own_number, own_offset, fields, data = _appended_xref_stream(second, first)
    assert int(fields["Prev"]) == first_startxref
    widths = [int(x) for x in fields["W"].split()]
    rows = _rows(data, widths)
    row_by_number = dict(zip(_index_numbers(fields["Index"]), rows, strict=True))
    assert row_by_number[own_number] == (1, own_offset, 0)

    reloaded = PDDocument(Loader.load_pdf(second))
    try:
        mb = reloaded.get_page(0).get_media_box()
        assert (mb.get_width(), mb.get_height()) == (555.0, 666.0)
    finally:
        reloaded.close()


def test_empty_increment_still_lists_self() -> None:
    """Even a no-dirty-object increment (PDFBox always appends a revision)
    now carries the self-entry — and the previously-degenerate all-zero /W
    case is gone because the self-row forces w1 >= 1 and w2 >= 1."""
    src = _source_bytes()
    doc = PDDocument(Loader.load_pdf(src))
    try:
        sink = io.BytesIO()
        doc.save_incremental(sink)
    finally:
        doc.close()
    out = sink.getvalue()

    own_number, own_offset, fields, data = _appended_xref_stream(out, src)
    widths = [int(x) for x in fields["W"].split()]
    assert widths[0] >= 1 and widths[1] >= 1
    assert sorted(_index_numbers(fields["Index"])) == [0, own_number]
    rows = _rows(data, widths)
    row_by_number = dict(zip(_index_numbers(fields["Index"]), rows, strict=True))
    assert row_by_number[own_number] == (1, own_offset, 0)
