"""Wave 1332 — coverage boost for ``pdmodel.fixup.processor.abstract_processor``.

Covers the abstract ``process`` raise-path so the module reaches >=95%.
"""

from __future__ import annotations

import pytest

from pypdfbox.pdmodel.fixup.processor.abstract_processor import AbstractProcessor
from pypdfbox.pdmodel.fixup.processor.pd_document_processor import (
    PDDocumentProcessor,
)


def test_abstract_processor_stores_document_reference() -> None:
    sentinel = object()
    processor = AbstractProcessor(sentinel)  # type: ignore[arg-type]
    assert processor.document is sentinel


def test_abstract_processor_is_pd_document_processor_subclass() -> None:
    assert issubclass(AbstractProcessor, PDDocumentProcessor)


def test_abstract_processor_process_raises_not_implemented_error() -> None:
    processor = AbstractProcessor(object())  # type: ignore[arg-type]
    with pytest.raises(NotImplementedError):
        processor.process()


def test_abstract_processor_subclass_overrides_process() -> None:
    calls: list[object] = []

    class _Concrete(AbstractProcessor):
        def process(self) -> None:
            calls.append(self.document)

    document = object()
    _Concrete(document).process()  # type: ignore[arg-type]
    assert calls == [document]
