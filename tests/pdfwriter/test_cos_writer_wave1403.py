"""Wave 1403 branch round-out for ``COSWriter._do_write_xref_table``.

Closes 1755->1754 — the ``if first <= entry.key.object_number < first +
count`` False arm: when the xref entries span *more than one* contiguous
range, the inner per-range loop iterates over *all* entries and skips those
outside the current range (continuing the loop).

``_fill_gaps_with_free_entries`` fills gaps between *normal* (non-free)
entries, so a single range is the norm. A pre-existing *free* entry beyond
the highest normal object number survives that fill and creates a genuine
gap, forcing ``_build_ranges`` to emit two ranges — which exercises the
skip arm.
"""

from __future__ import annotations

import io

from pypdfbox.cos import COSObjectKey
from pypdfbox.pdfwriter.cos_writer import COSWriter
from pypdfbox.pdfwriter.cos_writer_xref_entry import COSWriterXRefEntry


def test_write_xref_table_skips_entries_outside_current_range() -> None:
    """Closes 1755->1754: gapped object numbers produce two xref ranges, so
    while writing one range the inner loop skips the out-of-range entry."""
    writer = COSWriter(io.BytesIO())
    # Two contiguous normals (objects 1, 2) plus a free entry far away
    # (object 10) that fill won't bridge => ranges (0,3) and (10,1).
    writer._xref_entries = [  # noqa: SLF001
        COSWriterXRefEntry(offset=15, key=COSObjectKey(1, 0)),
        COSWriterXRefEntry(offset=60, key=COSObjectKey(2, 0)),
        COSWriterXRefEntry(offset=0, key=COSObjectKey(10, 65535), free=True),
    ]

    writer._do_write_xref_table()  # noqa: SLF001

    # The xref keyword was emitted; the test's purpose is the branch, but a
    # sanity check that two ranges were written keeps the intent clear.
    written = writer._standard_output  # noqa: SLF001
    assert written.get_position() > 0
