"""Closed-state exception family parity (wave 1485).

Pins the exception **type** and **message** raised when an operation is
attempted on a closed ``COSStream`` / ``COSWriter`` / ``PDDocument`` /
``FDFDocument``. Waves 1482-1483 aligned the ``pypdfbox.io`` classes
(Java ``IOException`` -> Python ``OSError`` with upstream-exact messages);
this wave does the same for the four higher-level closeables.

Oracle-confirmed upstream behavior (``oracle/probes/ClosedStateExceptionProbe.java``):

  * ``PDDocument.save`` after ``close`` -> ``IOException("Cannot save a
    document which has been closed")`` (PDDocument.java line 1025-1028) ->
    Python ``OSError`` with the same message.
  * ``COSStream.checkClosed`` -> ``IOException("COSStream has been closed
    and cannot be read. Perhaps its enclosing PDDocument has been
    closed?")`` (COSStream.java line 105-114) -> Python ``OSError``.
  * ``FDFDocument.save`` after ``close`` -> upstream does **NOT** guard
    (probe prints ``NO_THROW``); pypdfbox adds a defensive ``OSError``
    guard for symmetry with ``PDDocument`` (recorded as a divergence).

The standalone assertions pass without the oracle; the ``@requires_oracle``
test confirms the live PDFBox message byte-for-byte.
"""

from __future__ import annotations

import io

import pytest

from pypdfbox import PDDocument, PDPage
from pypdfbox.cos import COSDocument, COSStream
from pypdfbox.pdfwriter import COSWriter
from pypdfbox.pdmodel.fdf import FDFDocument

_COSSTREAM_CLOSED = (
    "COSStream has been closed and cannot be read. "
    "Perhaps its enclosing PDDocument has been closed?"
)
_SAVE_CLOSED = "Cannot save a document which has been closed"


# ---------- COSStream ----------


def test_cos_stream_set_raw_data_after_close_raises_oserror() -> None:
    s = COSStream()
    s.close()
    with pytest.raises(OSError, match=_COSSTREAM_CLOSED):
        s.set_raw_data(b"x")


def test_cos_stream_create_output_stream_after_close_raises_oserror() -> None:
    s = COSStream()
    s.close()
    with pytest.raises(OSError, match=_COSSTREAM_CLOSED):
        s.create_output_stream()


def test_cos_stream_create_raw_output_stream_after_close_raises_oserror() -> None:
    s = COSStream()
    s.close()
    with pytest.raises(OSError, match=_COSSTREAM_CLOSED):
        s.create_raw_output_stream()


# ---------- COSWriter ----------


def test_cos_writer_write_after_close_raises_oserror() -> None:
    writer = COSWriter(io.BytesIO())
    writer.close()
    with pytest.raises(OSError, match="COSWriter already closed"):
        writer.write(COSDocument())


# ---------- PDDocument ----------


def test_pd_document_save_after_close_raises_oserror() -> None:
    doc = PDDocument()
    doc.add_page(PDPage())
    doc.close()
    with pytest.raises(OSError, match=_SAVE_CLOSED):
        doc.save(io.BytesIO())


def test_pd_document_save_incremental_after_close_raises_oserror() -> None:
    doc = PDDocument()
    doc.close()
    with pytest.raises(OSError, match=_SAVE_CLOSED):
        doc.save_incremental(io.BytesIO())


def test_pd_document_split_after_close_raises_oserror() -> None:
    doc = PDDocument()
    doc.close()
    with pytest.raises(OSError, match="PDDocument has been closed"):
        doc.split()


def test_pd_document_extract_pages_after_close_raises_oserror() -> None:
    doc = PDDocument()
    doc.close()
    with pytest.raises(OSError, match="PDDocument has been closed"):
        doc.extract_pages(1, 1)


# ---------- FDFDocument (pypdfbox-only defensive guard) ----------


def test_fdf_document_save_after_close_raises_oserror() -> None:
    fdf = FDFDocument()
    fdf.close()
    with pytest.raises(OSError, match=_SAVE_CLOSED):
        fdf.save(io.BytesIO())


# ---------- Live oracle differential ----------


def test_save_closed_message_matches_oracle() -> None:
    """The PDDocument.save-after-close message is upstream-exact."""
    from tests.oracle.harness import oracle_available, run_probe_text

    if not oracle_available():
        pytest.skip("oracle (Java + pdfbox jar) not available")

    out = run_probe_text("ClosedStateExceptionProbe")
    lines = dict(
        line.split("=", 1) for line in out.splitlines() if "=" in line
    )
    # PDDocument.save raises IOException with the exact message pypdfbox pins.
    assert lines["pddocument.save"] == (
        "java.io.IOException|Cannot save a document which has been closed"
    )
    # FDFDocument.save has no upstream closed-state guard.
    assert lines["fdfdocument.save"] == "NO_THROW"
