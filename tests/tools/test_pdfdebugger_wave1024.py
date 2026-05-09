"""Wave 1024 coverage for pdfdebugger wave361 test helpers."""
from __future__ import annotations

from pathlib import Path

import pytest

import tests.tools.test_pdfdebugger_wave361 as wave361
from pypdfbox.cos import COSDocument


class _EmptyLoadedDocument:
    def __enter__(self) -> _EmptyLoadedDocument:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self._cos_doc.close()

    def __init__(self) -> None:
        self._cos_doc = COSDocument()

    def get_document(self) -> COSDocument:
        return self._cos_doc


def test_wave1024_first_stream_key_raises_when_no_stream(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        wave361.PDDocument,
        "load",
        lambda _path: _EmptyLoadedDocument(),
    )

    with pytest.raises(AssertionError, match="expected at least one indirect stream"):
        wave361._first_stream_key(Path("no-stream.pdf"))
