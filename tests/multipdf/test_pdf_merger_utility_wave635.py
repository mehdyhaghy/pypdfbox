from __future__ import annotations

import io
import logging

import pytest

from pypdfbox.io.random_access_read_buffer import RandomAccessReadBuffer
from pypdfbox.multipdf.pdf_merger_utility import (
    DocumentMergeMode,
    PDFMergerUtility,
)
from pypdfbox.pdmodel import PDDocument


def test_wave635_open_source_keeps_caller_owned_document_open() -> None:
    doc = PDDocument()

    resolved, owns = PDFMergerUtility._open_source(doc)  # noqa: SLF001

    assert resolved is doc
    assert owns is False
    assert doc.is_closed() is False

    doc.close()


def test_wave635_open_source_loads_supported_inputs_and_rejects_bad_streams(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    loaded_sources: list[object] = []

    def fake_load(cls: type[PDDocument], source: object) -> object:
        del cls
        loaded_sources.append(source)
        return f"doc-{len(loaded_sources)}"

    monkeypatch.setattr(PDDocument, "load", classmethod(fake_load))

    random_access = RandomAccessReadBuffer(b"%PDF")
    binary_stream = io.BytesIO(b"stream-pdf")

    assert PDFMergerUtility._open_source(b"bytes-pdf") == ("doc-1", True)  # noqa: SLF001
    assert PDFMergerUtility._open_source(memoryview(b"memory-pdf")) == (  # noqa: SLF001
        "doc-2",
        True,
    )
    assert PDFMergerUtility._open_source(random_access) == ("doc-3", True)  # noqa: SLF001
    assert PDFMergerUtility._open_source(binary_stream) == ("doc-4", True)  # noqa: SLF001

    assert loaded_sources[:3] == [b"bytes-pdf", b"memory-pdf", random_access]
    assert loaded_sources[3] == b"stream-pdf"

    with pytest.raises(TypeError, match="binary stream source read"):
        PDFMergerUtility._open_source(io.StringIO("not bytes"))  # noqa: SLF001
    with pytest.raises(TypeError, match="unsupported source type"):
        PDFMergerUtility._open_source(object())  # noqa: SLF001


def test_wave635_merge_documents_without_sources_stages_options_and_returns(
    caplog: pytest.LogCaptureFixture,
) -> None:
    util = PDFMergerUtility()
    stream_cache = object()
    compress_params = object()
    util.set_document_merge_mode(DocumentMergeMode.OPTIMIZE_RESOURCES_MODE)

    with caplog.at_level(logging.INFO, logger="pypdfbox.multipdf.pdf_merger_utility"):
        util.merge_documents(
            stream_cache_create_function=stream_cache,
            compress_parameters=compress_params,
        )

    assert util.get_stream_cache_create_function() is stream_cache
    assert util.get_compress_parameters() is compress_params
    assert "falling back to PDFBOX_LEGACY_MODE" in caplog.text


def test_wave635_merge_random_access_requires_random_access_sources() -> None:
    util = PDFMergerUtility()

    with pytest.raises(TypeError, match="every source must be a RandomAccessRead"):
        util.merge_documents_random_access_read([b"not-random-access"])  # type: ignore[list-item]

