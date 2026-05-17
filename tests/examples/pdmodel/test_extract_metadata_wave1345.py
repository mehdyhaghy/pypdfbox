"""Wave 1345 — coverage round-out for :class:`ExtractMetadata`.

Targets the remaining uncovered lines:

* the trivial ``__init__`` body (line 27);
* the ``XmpParsingException`` rescue branch (lines 49-50);
* the populated ``list_calendar`` branch (lines 111-113).
"""

from __future__ import annotations

import datetime as _dt
from pathlib import Path

import pytest

from pypdfbox.examples.pdmodel import extract_metadata
from pypdfbox.examples.pdmodel.extract_metadata import ExtractMetadata
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.xmpbox import XmpParsingException


def test_constructor_is_inert() -> None:
    """The ``__init__`` body is just ``pass`` — line 27."""
    assert ExtractMetadata() is not None


def test_list_calendar_with_items_prints_dates(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A non-None list iterates and formats each entry (lines 111-113)."""
    dates = [_dt.date(2024, 1, 15), _dt.date(2025, 6, 30)]
    ExtractMetadata.list_calendar("Dates:", dates)
    out = capsys.readouterr().out
    assert "Dates:" in out
    assert "Jan 15, 2024" in out
    assert "Jun 30, 2025" in out


def test_main_swallows_xmp_parsing_exception(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """When the XMP parser raises :class:`XmpParsingException`, the
    runner logs to stderr and continues — lines 49-50."""
    # Build a PDF that carries an XMP metadata stream (any bytes will do —
    # we'll route the parser past the bytes via the monkeypatch below).
    pdf = tmp_path / "xmp-bad.pdf"
    with PDDocument() as doc:
        doc.add_page(PDPage())
        info = doc.get_document_information()
        info.set_title("XMP Test")
        doc.save(pdf)

    # Round-trip through AddMetadataFromDocInfo so the document carries a
    # /Metadata stream — that's the only branch where the XmpParsingException
    # is reachable from ExtractMetadata.main.
    from pypdfbox.examples.pdmodel.add_metadata_from_doc_info import (
        AddMetadataFromDocInfo,
    )

    stamped = tmp_path / "xmp-stamped.pdf"
    AddMetadataFromDocInfo.main([str(pdf), str(stamped)])

    # Force the DOM parser to raise XmpParsingException — exercises the
    # rescue branch without needing pathological input bytes.
    class _BadParser:
        def parse(self, _raw: bytes) -> None:
            raise XmpParsingException("bad xmp")

    monkeypatch.setattr(extract_metadata, "DomXmpParser", _BadParser)

    ExtractMetadata.main([str(stamped)])
    err = capsys.readouterr().err
    assert "error occurred when parsing the metadata" in err
    assert "bad xmp" in err
