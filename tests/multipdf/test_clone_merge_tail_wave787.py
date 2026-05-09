from __future__ import annotations

import io
import logging

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSObject, COSStream
from pypdfbox.multipdf import PDFCloneUtility, PDFMergerUtility
from pypdfbox.pdmodel import PDDocument


class _Wrap:
    def __init__(self, base: COSArray | COSDictionary) -> None:
        self._base = base

    def get_cos_object(self) -> COSArray | COSDictionary:
        return self._base


def test_wave787_clone_unresolved_reference_returns_none() -> None:
    with PDDocument() as destination:
        cloner = PDFCloneUtility(destination)

        assert cloner.clone_for_new_document(COSObject(787, 0)) is None


def test_wave787_clone_array_and_stream_indirect_self_references() -> None:
    with PDDocument() as destination:
        cloner = PDFCloneUtility(destination)
        array = COSArray()
        array.add(COSObject(1, 0, resolved=array))

        stream = COSStream()
        stream.set_item("Self", COSObject(2, 0, resolved=stream))

        cloned_array = cloner.clone_for_new_document(array)
        cloned_stream = cloner.clone_for_new_document(stream)

        assert isinstance(cloned_array, COSArray)
        assert cloned_array.get(0) is cloned_array
        assert isinstance(cloned_stream, COSStream)
        assert cloned_stream.get_dictionary_object("Self") is cloned_stream


def test_wave787_clone_merge_noops_for_none_and_unresolved_source() -> None:
    with PDDocument() as destination:
        cloner = PDFCloneUtility(destination)
        target = COSArray([COSInteger.get(1)])

        cloner.clone_merge(None, _Wrap(target))
        cloner._clone_merge_cos_base(COSObject(3, 0), target, set())  # noqa: SLF001

        assert target.size() == 1
        assert target.get(0) == COSInteger.get(1)


def test_wave787_merger_finally_logs_owned_source_close_failure(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    class BadSource:
        def close(self) -> None:
            raise OSError("source close failed")

    def fail_append(
        self: PDFMergerUtility,
        destination: PDDocument,
        source: object,
    ) -> None:
        raise RuntimeError("append failed")

    util = PDFMergerUtility()
    util.add_source(b"%PDF-placeholder")
    util.set_destination_stream(io.BytesIO())
    monkeypatch.setattr(
        PDFMergerUtility,
        "_open_source",
        staticmethod(lambda source: (BadSource(), True)),
    )
    monkeypatch.setattr(PDFMergerUtility, "append_document", fail_append)

    with (
        caplog.at_level(logging.ERROR, logger="pypdfbox.multipdf.pdf_merger_utility"),
        pytest.raises(RuntimeError, match="append failed"),
    ):
        util.merge_documents()

    assert "error closing source PDDocument" in caplog.text
