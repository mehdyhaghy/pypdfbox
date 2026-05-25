"""Branch coverage for :class:`PDFXRefStream` — wave 1400.

Closes residual partial branches in
``pypdfbox/pdfparser/pdf_xref_stream.py``:

* The direct-forcing loop in ``get_stream`` skips entries whose value
  resolves to ``None`` (typed COSNull) — branch (110 → 104).
"""

from __future__ import annotations

from pypdfbox.cos import (
    COSDictionary,
    COSDocument,
    COSName,
    COSNull,
    COSObjectKey,
    COSStream,
)
from pypdfbox.pdfparser import PDFXRefStream
from pypdfbox.pdfparser.xref import NormalXReference


def test_get_stream_skips_set_direct_when_value_resolves_to_none() -> None:
    """When a trailer/xref-stream entry holds ``COSNull.NULL`` (or any
    value whose ``get_dictionary_object`` resolution returns ``None``),
    the direct-forcing loop must NOT call ``set_direct`` on ``None``.

    Closes branch (110 → 104) in pdf_xref_stream."""
    doc = COSDocument()
    try:
        xs = PDFXRefStream(doc)
        xs.set_size(5)
        # Add a real entry so the body-write path runs.
        body_stream = COSStream()
        try:
            xs.add_entry(NormalXReference(0, COSObjectKey(1, 0), body_stream))
            # Stash a key whose value resolves to None (COSNull).
            xs._stream.set_item(  # noqa: SLF001
                COSName.get_pdf_name("MyNullEntry"), COSNull.NULL
            )
            # Must not raise — set_direct should be skipped for the None
            # resolution.
            stream = xs.get_stream()
            assert stream is not None
        finally:
            body_stream.close()
    finally:
        doc.close()


def test_get_stream_calls_set_direct_on_non_none_entries() -> None:
    """Positive control: entries whose value resolves to a real COSBase
    do get ``set_direct(True)`` invoked. Skipping is value-driven, not
    blanket-skip-all."""
    doc = COSDocument()
    try:
        xs = PDFXRefStream(doc)
        xs.set_size(5)
        body_stream = COSStream()
        try:
            xs.add_entry(NormalXReference(0, COSObjectKey(1, 0), body_stream))
            extra = COSDictionary()
            extra.set_int("Extra", 7)
            xs._stream.set_item(  # noqa: SLF001
                COSName.get_pdf_name("MyExtra"), extra
            )
            xs.get_stream()
            # The extra dict was visited and forced direct.
            assert extra.is_direct() is True
        finally:
            body_stream.close()
    finally:
        doc.close()
