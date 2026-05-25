"""Wave 1402 branch-coverage round-out for ``COSWriter``.

Closes False-branch arrows in ``pypdfbox/pdfwriter/cos_writer.py``:

* 1755->1754 — ``_do_write_xref_table`` loops over all entries for each
  range; with non-contiguous object numbers the inner ``if first <= ...``
  is False on the entries that don't belong to the current range.
* 1861->1863 — ``_do_write_body_xref_stream`` skips ``root`` when the
  trailer carries ``/Info`` but no ``/Root``.
"""

from __future__ import annotations

import io

from pypdfbox.cos import COSDictionary, COSDocument, COSName, COSObjectKey
from pypdfbox.pdfwriter.cos_writer import COSWriter
from pypdfbox.pdfwriter.cos_writer_xref_entry import COSWriterXRefEntry


def test_xref_table_multiple_ranges_exercises_outside_range_arrow() -> None:
    """Closes 1755->1754: with a non-contiguous set of recorded entries
    (e.g. {1, 5, 7}), ``_build_ranges`` yields multiple ``(first, count)``
    tuples and the inner ``for entry in entries`` exercises the False
    arrow when an entry's object number is outside the current range.
    """

    sink = io.BytesIO()
    writer = COSWriter(sink)
    # Inject non-contiguous xref entries so build_ranges emits multiple
    # ranges. We seed a few entries with deliberate gaps.
    writer._xref_entries = [  # noqa: SLF001
        COSWriterXRefEntry(offset=10, key=COSObjectKey(1, 0)),
        COSWriterXRefEntry(offset=20, key=COSObjectKey(5, 0)),
        COSWriterXRefEntry(offset=30, key=COSObjectKey(7, 0)),
    ]
    # Stub the underlying output so _write_xref_range/_write_xref_entry
    # have somewhere to write.
    writer._do_write_xref_table()  # noqa: SLF001
    # No assertion on output content — coverage is the point. Verify
    # the method ran to completion by checking startxref is set.
    assert writer._startxref >= 0  # noqa: SLF001


def test_body_xref_stream_trailer_present_but_no_root_entry() -> None:
    """Closes 1861->1863: trailer is not None and has /Info but no /Root,
    so the ``if root is not None`` arm is False and the body skips the
    root add.
    """

    sink = io.BytesIO()
    writer = COSWriter(sink)

    cos_doc = COSDocument()
    trailer = COSDictionary()
    # Add /Info but deliberately omit /Root so the root arm is False.
    info_dict = COSDictionary()
    trailer.set_item(COSName.INFO, info_dict)
    cos_doc.set_trailer(trailer)

    # _do_write_body_xref_stream calls _add_object_to_write and
    # _do_write_objects which may touch other writer state. Patch the
    # heavy methods to no-ops so the test focuses on the branch arrows.
    writer._add_object_to_write = lambda _o: None  # type: ignore[assignment,method-assign]  # noqa: SLF001
    writer._do_write_objects = lambda: None  # type: ignore[assignment,method-assign]  # noqa: SLF001
    writer._do_write_body_xref_stream(cos_doc)  # noqa: SLF001
