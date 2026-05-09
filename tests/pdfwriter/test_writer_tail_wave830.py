from __future__ import annotations

import io

import pytest

from pypdfbox.cos import COSInteger, COSObjectKey
from pypdfbox.pdfwriter import COSWriter
from pypdfbox.pdfwriter.cos_standard_output_stream import COSStandardOutputStream
from pypdfbox.pdfwriter.cos_writer_xref_entry import COSWriterXRefEntry


def test_wave830_writer_exposes_raw_and_standard_outputs() -> None:
    sink = io.BytesIO()
    writer = COSWriter(sink)

    assert writer.get_output() is sink
    assert isinstance(writer.get_standard_output(), COSStandardOutputStream)


def test_wave830_started_stream_tracking_uses_live_set() -> None:
    writer = COSWriter(io.BytesIO())
    started = writer.get_started_streams()
    marker = object()

    started.add(marker)
    assert writer.has_started_streams() is True

    writer.clear_started_streams()
    assert started == set()
    assert writer.has_started_streams() is False


def test_wave830_add_xref_entry_updates_both_aliases() -> None:
    writer = COSWriter(io.BytesIO())
    entry = COSWriterXRefEntry(offset=830, key=COSObjectKey(8, 30))

    writer.add_xref_entry(entry)

    assert writer.get_xref_entries() == [entry]
    assert writer.get_x_ref_entries() is writer.get_xref_entries()


def test_wave830_add_xref_entry_rejects_non_entry() -> None:
    writer = COSWriter(io.BytesIO())

    with pytest.raises(TypeError, match="COSWriterXRefEntry"):
        writer.add_xref_entry(COSInteger.get(1))  # type: ignore[arg-type]


def test_wave830_xref_entry_le_ge_ignore_generation_offset_and_free() -> None:
    entry = COSWriterXRefEntry(offset=99, key=COSObjectKey(3, 7), free=True)
    same_object = COSWriterXRefEntry(offset=1, key=COSObjectKey(3, 0))
    later = COSWriterXRefEntry(offset=0, key=COSObjectKey(5, 0))

    assert entry <= same_object
    assert entry >= same_object
    assert entry <= later
    assert later >= entry
